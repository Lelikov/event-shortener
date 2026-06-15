from datetime import UTC, datetime

from pydantic import BaseModel

from event_shortener.dto.short_url import UpsertShortUrlDTO


def _epoch_to_dt(value: float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


class ShortenRequest(BaseModel):
    long_url: str
    external_id: str
    # Float epoch seconds on the wire; stored as timestamptz.
    expires_at: float | None = None
    not_before: float | None = None

    def to_dto(self) -> UpsertShortUrlDTO:
        return UpsertShortUrlDTO(
            long_url=self.long_url,
            external_id=self.external_id,
            not_before=_epoch_to_dt(self.not_before),
            expires_at=_epoch_to_dt(self.expires_at),
        )


class IdentResponse(BaseModel):
    ident: str


class IdentStatsResponse(BaseModel):
    ident: str
    click_count: int
