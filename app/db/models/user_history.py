from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserHistory(Base):
    """One row per (user, anime) — `viewed_at` is bumped to now on every
    view rather than logging every individual view, so "recently viewed"
    stays a clean distinct list."""

    __tablename__ = "user_history"
    __table_args__ = (UniqueConstraint("user_id", "anime_id", name="uq_user_history"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    anime: Mapped["Anime"] = relationship(lazy="joined")  # noqa: F821
