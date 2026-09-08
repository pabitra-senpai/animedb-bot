from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VoiceActor(Base):
    __tablename__ = "voice_actors"

    id: Mapped[int] = mapped_column(primary_key=True)
    anilist_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    name_full: Mapped[str] = mapped_column(String(255), nullable=False)
    name_native: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VoiceActor id={self.id} name={self.name_full!r}>"


class CharacterVoiceActor(Base):
    """A character can be voiced by different actors in different anime
    (e.g. a franchise reboot), so the link is scoped per anime+character."""

    __tablename__ = "character_voice_actors"
    __table_args__ = (
        UniqueConstraint(
            "anime_id", "character_id", "voice_actor_id", "language",
            name="uq_character_voice_actor",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anime_id: Mapped[int] = mapped_column(
        ForeignKey("anime.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voice_actor_id: Mapped[int] = mapped_column(
        ForeignKey("voice_actors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="JAPANESE")

    voice_actor: Mapped[VoiceActor] = relationship(lazy="joined")
