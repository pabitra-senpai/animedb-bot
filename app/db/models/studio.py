from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Studio(Base):
    __tablename__ = "studios"

    id: Mapped[int] = mapped_column(primary_key=True)

    anilist_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    mal_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Studio id={self.id} name={self.name!r}>"


class AnimeStudio(Base):
    __tablename__ = "anime_studios"
    __table_args__ = (
        UniqueConstraint("anime_id", "studio_id", "role", name="uq_anime_studio_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    studio_id: Mapped[int] = mapped_column(
        ForeignKey("studios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # e.g. "studio" (animation production) vs "producer"-style credit at the studio level
    role: Mapped[str] = mapped_column(String(50), default="studio", nullable=False)

    studio: Mapped[Studio] = relationship(lazy="joined")
