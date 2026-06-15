import structlog

from event_shortener.adapters.short_url_db import IdentCollisionError
from event_shortener.dto.short_url import ShortUrlDTO, UpsertShortUrlDTO
from event_shortener.errors import IdentGenerationError
from event_shortener.ident import generate_ident
from event_shortener.interfaces.shortener import IShortUrlDBAdapter


logger = structlog.get_logger(__name__)

# Bounded retries when a freshly minted ident collides with an existing row.
# At 62^7 keyspace and the system's small scale a single retry is already
# astronomically unlikely to be needed; five gives ample headroom.
MAX_IDENT_ATTEMPTS = 5


class ShortenerController:
    def __init__(self, db_adapter: IShortUrlDBAdapter) -> None:
        self._db = db_adapter

    async def shorten(self, dto: UpsertShortUrlDTO) -> tuple[str, bool]:
        """Return (ident, created) — created=False on an idempotent re-call."""
        # Idempotent by external_id: a redelivery of the same request returns the
        # ident already minted rather than creating a second row.
        existing = await self._db.get_by_external_id(dto.external_id)
        if existing is not None:
            logger.info("Shorten idempotent hit", external_id=dto.external_id, ident=existing.ident)
            return existing.ident, False

        for attempt in range(1, MAX_IDENT_ATTEMPTS + 1):
            ident = generate_ident()
            try:
                created = await self._db.insert(ident, dto)
            except IdentCollisionError:
                logger.warning("Ident collision, regenerating", attempt=attempt, ident=ident)
                continue
            logger.info("Short URL created", external_id=dto.external_id, ident=created.ident)
            return created.ident, True

        raise IdentGenerationError(
            f"Could not allocate a unique ident after {MAX_IDENT_ATTEMPTS} attempts",
        )

    async def get_ident(self, external_id: str) -> str | None:
        existing = await self._db.get_by_external_id(external_id)
        if existing is None:
            return None
        return existing.ident

    async def update(self, old_external_id: str, dto: UpsertShortUrlDTO) -> str | None:
        updated = await self._db.update_by_external_id(old_external_id, dto)
        if updated is None:
            return None
        return updated.ident

    async def delete(self, external_id: str) -> bool:
        return await self._db.delete_by_external_id(external_id)

    async def resolve(self, ident: str) -> ShortUrlDTO | None:
        return await self._db.get_by_ident(ident)

    async def register_click(self, ident: str) -> None:
        await self._db.increment_click(ident)
