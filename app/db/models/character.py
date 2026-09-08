from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    anilist_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    name_full: Mapped[str] = mapped_column(String(255), nullable=False)
    name_native: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Character id={self.id} name={self.name_full!r}>"


class AnimeCharacter(Base):
    __tablename__ = "anime_characters"
    __table_args__ = (
        UniqueConstraint("anime_id", "character_id", name="uq_anime_character"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # AniList role values: MAIN, SUPPORTING, BACKGROUND
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="BACKGROUND")

    character: Mapped[Character] = relationship(lazy="joined")
