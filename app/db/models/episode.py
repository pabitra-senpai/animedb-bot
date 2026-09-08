from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Episode(TimestampMixin, Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("anime_id", "episode_number", name="uq_anime_episode_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # External episode identifiers where a provider exposes them (nullable —
    # not every provider gives per-episode IDs).
    anilist_episode_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    kitsu_episode_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    anime: Mapped["Anime"] = relationship(back_populates="episodes_rel")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Episode anime_id={self.anime_id} number={self.episode_number}>"
