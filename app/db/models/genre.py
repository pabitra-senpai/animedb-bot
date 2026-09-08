from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Genre id={self.id} name={self.name!r}>"


class AnimeGenre(Base):
    __tablename__ = "anime_genres"
    __table_args__ = (UniqueConstraint("anime_id", "genre_id", name="uq_anime_genre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    genre_id: Mapped[int] = mapped_column(
        ForeignKey("genres.id", ondelete="CASCADE"), nullable=False, index=True
    )

    genre: Mapped[Genre] = relationship(lazy="joined")
