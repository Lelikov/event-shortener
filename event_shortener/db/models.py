from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from event_shortener.db.base import Base


class ShortUrl(Base):
    """Single table backing the shortener.

    Queries are raw SQL in the adapter; this ORM model exists only so Alembic
    can autogenerate / detect drift against the live schema.
    """

    __tablename__ = "short_urls"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ident: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    long_url: Mapped[str] = mapped_column(Text, nullable=False)
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        server_onupdate=text("now()"),
    )
    click_count: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("ident", name="uq_short_urls_ident"),
        UniqueConstraint("external_id", name="uq_short_urls_external_id"),
        # Redirect is a single indexed lookup on ident; the unique constraint
        # already provides that index, so no extra index is declared.
        Index("ix_short_urls_external_id", "external_id"),
    )
