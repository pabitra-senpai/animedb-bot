from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Anime(TimestampMixin, Base):
    __tablename__ = "anime"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- External identity mapping ---
    anilist_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    mal_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    kitsu_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    simkl_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True, index=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Titles ---
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    english_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    native_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    romaji_title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Descriptive ---
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    trailer_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # --- Classification ---
    format: Mapped[str | None] = mapped_column(String(50), nullable=True)  # TV, MOVIE, OVA, ...
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ONGOING, FINISHED, ...
    season: Mapped[str | None] = mapped_column(String(20), nullable=True)  # WINTER/SPRING/SUMMER/FALL
    season_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_material: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Ranking / popularity ---
    score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    favourites_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)

    # --- Country/language metadata ---
    country_of_origin: Mapped[str | None] = mapped_column(String(10), nullable=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships (loaded explicitly by services, not eagerly by default) ---
    titles: Mapped[list["AnimeTitle"]] = relationship(
        back_populates="anime", cascade="all, delete-orphan"
    )
    episodes_rel: Mapped[list["Episode"]] = relationship(
        back_populates="anime", cascade="all, delete-orphan", order_by="Episode.episode_number"
    )
    genre_links: Mapped[list["AnimeGenre"]] = relationship(cascade="all, delete-orphan")
    studio_links: Mapped[list["AnimeStudio"]] = relationship(cascade="all, delete-orphan")
    character_links: Mapped[list["AnimeCharacter"]] = relationship(cascade="all, delete-orphan")
    staff_links: Mapped[list["AnimeStaff"]] = relationship(cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Anime id={self.id} title={self.title!r}>"
