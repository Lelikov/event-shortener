from typing import TYPE_CHECKING

import structlog
from sqlalchemy.exc import IntegrityError

from event_shortener.dto.short_url import ShortUrlDTO, UpsertShortUrlDTO
from event_shortener.interfaces.sql import ISqlExecutor


if TYPE_CHECKING:
    from sqlalchemy.engine import RowMapping


logger = structlog.get_logger(__name__)

_COLUMNS = "id, ident, external_id, long_url, not_before, expires_at, created_at, updated_at, click_count"


class IdentCollisionError(Exception):
    """The generated ident already exists; the caller should regenerate and retry."""


def _from_row(row: RowMapping) -> ShortUrlDTO:
    return ShortUrlDTO(
        id=row["id"],
        ident=row["ident"],
        external_id=row["external_id"],
        long_url=row["long_url"],
        not_before=row["not_before"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        click_count=row["click_count"],
    )


def _is_ident_conflict(error: IntegrityError) -> bool:
    # asyncpg surfaces the violated constraint name in the exception text; the
    # ident constraint and the external_id constraint must be told apart so an
    # ident clash retries while a duplicate external_id is handled by the caller.
    return "uq_short_urls_ident" in str(error.orig)


class ShortUrlDBAdapter:
    def __init__(self, sql_executor: ISqlExecutor) -> None:
        self._sql = sql_executor

    async def get_by_external_id(self, external_id: str) -> ShortUrlDTO | None:
        row = await self._sql.fetch_one(
            f"SELECT {_COLUMNS} FROM short_urls WHERE external_id = :external_id",  # noqa: S608
            {"external_id": external_id},
        )
        if row is None:
            return None
        return _from_row(row)

    async def get_by_ident(self, ident: str) -> ShortUrlDTO | None:
        row = await self._sql.fetch_one(
            f"SELECT {_COLUMNS} FROM short_urls WHERE ident = :ident",  # noqa: S608
            {"ident": ident},
        )
        if row is None:
            return None
        return _from_row(row)

    async def insert(self, ident: str, dto: UpsertShortUrlDTO) -> ShortUrlDTO:
        try:
            row = await self._sql.fetch_one(
                f"""
                INSERT INTO short_urls (ident, external_id, long_url, not_before, expires_at)
                VALUES (:ident, :external_id, :long_url, :not_before, :expires_at)
                RETURNING {_COLUMNS}
                """,  # noqa: S608
                {
                    "ident": ident,
                    "external_id": dto.external_id,
                    "long_url": dto.long_url,
                    "not_before": dto.not_before,
                    "expires_at": dto.expires_at,
                },
            )
        except IntegrityError as e:
            if _is_ident_conflict(e):
                raise IdentCollisionError(ident) from e
            raise
        return _from_row(row)

    async def update_by_external_id(self, old_external_id: str, dto: UpsertShortUrlDTO) -> ShortUrlDTO | None:
        # ident is intentionally preserved; only the mutable fields (incl. the
        # new external_id) are written.
        row = await self._sql.fetch_one(
            f"""
            UPDATE short_urls
            SET external_id = :external_id,
                long_url = :long_url,
                not_before = :not_before,
                expires_at = :expires_at,
                updated_at = now()
            WHERE external_id = :old_external_id
            RETURNING {_COLUMNS}
            """,  # noqa: S608
            {
                "old_external_id": old_external_id,
                "external_id": dto.external_id,
                "long_url": dto.long_url,
                "not_before": dto.not_before,
                "expires_at": dto.expires_at,
            },
        )
        if row is None:
            return None
        return _from_row(row)

    async def increment_click(self, ident: str) -> None:
        await self._sql.execute(
            "UPDATE short_urls SET click_count = click_count + 1 WHERE ident = :ident",
            {"ident": ident},
        )

    async def delete_by_external_id(self, external_id: str) -> bool:
        row = await self._sql.fetch_one(
            "DELETE FROM short_urls WHERE external_id = :external_id RETURNING id",
            {"external_id": external_id},
        )
        return row is not None
