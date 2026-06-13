"""Controller-level tests for ident collision retry.

No DB needed: the adapter seam is faked so the unique-violation path is
deterministic.
"""

from datetime import UTC, datetime

import pytest

from event_shortener.adapters.short_url_db import IdentCollisionError
from event_shortener.controllers.shortener import MAX_IDENT_ATTEMPTS, ShortenerController
from event_shortener.dto.short_url import ShortUrlDTO, UpsertShortUrlDTO
from event_shortener.errors import IdentGenerationError


def _dto(external_id: str = "ext") -> UpsertShortUrlDTO:
    return UpsertShortUrlDTO(long_url="https://x.example", external_id=external_id, not_before=None, expires_at=None)


def _record(ident: str, external_id: str) -> ShortUrlDTO:
    now = datetime.now(UTC)
    return ShortUrlDTO(
        id=1,
        ident=ident,
        external_id=external_id,
        long_url="https://x.example",
        not_before=None,
        expires_at=None,
        created_at=now,
        updated_at=now,
    )


class CollidingDB:
    """Raises IdentCollisionError for the first `collisions` inserts, then succeeds."""

    def __init__(self, collisions: int) -> None:
        self.remaining = collisions
        self.insert_calls = 0

    async def get_by_external_id(self, external_id: str) -> ShortUrlDTO | None:
        return None

    async def insert(self, ident: str, dto: UpsertShortUrlDTO) -> ShortUrlDTO:
        self.insert_calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise IdentCollisionError(ident)
        return _record(ident, dto.external_id)


async def test_collision_retries_then_succeeds() -> None:
    db = CollidingDB(collisions=2)
    controller = ShortenerController(db)
    ident, created = await controller.shorten(_dto())
    assert created is True
    assert len(ident) == 7
    assert db.insert_calls == 3  # 2 collisions + 1 success


async def test_collision_exhausts_budget_raises() -> None:
    db = CollidingDB(collisions=MAX_IDENT_ATTEMPTS)
    controller = ShortenerController(db)
    with pytest.raises(IdentGenerationError):
        await controller.shorten(_dto())
    assert db.insert_calls == MAX_IDENT_ATTEMPTS


async def test_idempotent_when_external_id_exists() -> None:
    class ExistingDB:
        async def get_by_external_id(self, external_id: str) -> ShortUrlDTO:
            return _record("keep123", external_id)

        async def insert(self, ident: str, dto: UpsertShortUrlDTO) -> ShortUrlDTO:  # pragma: no cover
            raise AssertionError("insert must not be called on idempotent hit")

    ident, created = await ShortenerController(ExistingDB()).shorten(_dto("dup"))
    assert ident == "keep123"
    assert created is False
