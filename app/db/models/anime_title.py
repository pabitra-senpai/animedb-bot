from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnimeTitle(Base):
    """Alternative titles used for search matching (romaji/native/english/synonyms)."""

    __tablename__ = "anime_titles"

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # e.g. "romaji", "english", "native", "synonym"
    title_type: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Lowercased, whitespace-normalized form for fast, consistent search
    # matching — populated by the search service in Phase 4.
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    anime: Mapped["Anime"] = relationship(back_populates="titles")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AnimeTitle anime_id={self.anime_id} title={self.title!r}>"
