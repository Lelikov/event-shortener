from functools import lru_cache

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    debug: bool = False
    log_level: str = "INFO"

    # asyncpg URL, e.g. postgresql+asyncpg://postgres:postgres@pg-shortener:5432/event_shortener
    postgres_dsn: PostgresDsn = Field(strict=True)

    # Static bearer key that gates every /api/v1/* route (constant-time compared).
    shortener_api_key: str = Field(...)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log_level: {v!r}. Must be one of {sorted(valid_levels)}")
        return upper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Single process-wide Settings instance (also used by the DI container)."""
    return Settings()
