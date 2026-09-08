from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    anilist_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    name_full: Mapped[str] = mapped_column(String(255), nullable=False)
    name_native: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Staff id={self.id} name={self.name_full!r}>"


class AnimeStaff(Base):
    __tablename__ = "anime_staff"
    __table_args__ = (
        UniqueConstraint("anime_id", "staff_id", "role", name="uq_anime_staff_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Free-text credit, e.g. "Director", "Original Creator", "Music"
    role: Mapped[str] = mapped_column(String(100), nullable=False)

    staff: Mapped[Staff] = relationship(lazy="joined")
