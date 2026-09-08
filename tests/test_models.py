"""
Model/relationship tests against an in-memory SQLite database.

This keeps `pytest` runnable with no external services. The migration
path itself (Alembic -> real PostgreSQL) is verified separately — see
README "Database migrations" — since SQLite and Postgres DDL diverge
slightly and autogenerate must target real Postgres.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, AnimeGenre, AnimeStudio, AnimeTitle, Episode, Genre, Studio, User


@pytest.mark.asyncio
async def test_anime_with_titles_and_episodes(session: AsyncSession) -> None:
    anime = Anime(anilist_id=21, title="One Piece", format="TV", status="ONGOING")
    session.add(anime)
    await session.flush()

    session.add_all(
        [
            AnimeTitle(anime_id=anime.id, title="One Piece", title_type="romaji", normalized_title="one piece"),
            Episode(anime_id=anime.id, episode_number=1, title="Romance Dawn"),
            Episode(anime_id=anime.id, episode_number=2, title="The Great Swordsman"),
        ]
    )
    await session.commit()

    result = await session.execute(select(Anime).where(Anime.anilist_id == 21))
    fetched = result.scalar_one()
    await session.refresh(fetched, attribute_names=["titles", "episodes_rel"])

    assert fetched.title == "One Piece"
    assert len(fetched.titles) == 1
    assert [e.episode_number for e in fetched.episodes_rel] == [1, 2]


@pytest.mark.asyncio
async def test_anime_genre_and_studio_associations(session: AsyncSession) -> None:
    anime = Anime(title="Frieren", format="TV")
    genre = Genre(name="Fantasy")
    studio = Studio(name="Madhouse")
    session.add_all([anime, genre, studio])
    await session.flush()

    session.add(AnimeGenre(anime_id=anime.id, genre_id=genre.id))
    session.add(AnimeStudio(anime_id=anime.id, studio_id=studio.id, role="studio"))
    await session.commit()

    result = await session.execute(select(AnimeGenre).where(AnimeGenre.anime_id == anime.id))
    link = result.scalar_one()
    assert link.genre.name == "Fantasy"


@pytest.mark.asyncio
async def test_user_defaults(session: AsyncSession) -> None:
    user = User(telegram_user_id=42, first_name="Pabitra")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.is_admin is False
    assert user.is_banned is False
    assert user.notifications_enabled is True
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_duplicate_anime_genre_link_rejected(session: AsyncSession) -> None:
    anime = Anime(title="Bleach", format="TV")
    genre = Genre(name="Action")
    session.add_all([anime, genre])
    await session.flush()

    session.add(AnimeGenre(anime_id=anime.id, genre_id=genre.id))
    await session.commit()

    session.add(AnimeGenre(anime_id=anime.id, genre_id=genre.id))
    with pytest.raises(Exception):
        await session.commit()
