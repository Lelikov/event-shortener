from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UpsertShortUrlDTO:
    """Inbound create/update payload (timestamps already decoded to aware datetimes)."""

    long_url: str
    external_id: str
    not_before: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True)
class ShortUrlDTO:
    id: int
    ident: str
    external_id: str
    long_url: str
    not_before: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    click_count: int = 0
