from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, AnimeGenre
from app.db.repositories.anime_repository import upsert_anime_from_jikan
from app.services.jikan_normalizer import normalize_jikan_anime

SAMPLE = {
    "mal_id": 999,
    "title": "Obscure Show",
    "title_english": None,
    "synopsis": "A show only Jikan knows about.",
    "type": "TV",
    "status": "Finished Airing",
    "episodes": 12,
    "score": 7.1,
    "images": {"jpg": {"large_image_url": "https://example.com/obscure.jpg"}},
    "genres": [{"name": "Drama"}, {"name": "Mystery"}],
}


@pytest.mark.asyncio
async def test_upsert_creates_anime_with_genres(session: AsyncSession) -> None:
    normalized = normalize_jikan_anime(SAMPLE)
    anime = await upsert_anime_from_jikan(session, normalized)
    await session.commit()

    assert anime.id is not None
    assert anime.mal_id == 999
    assert anime.anilist_id is None
    assert anime.title == "Obscure Show"
    assert anime.last_synced_at is not None

    genres = (await session.execute(select(AnimeGenre).where(AnimeGenre.anime_id == anime.id))).scalars().all()
    assert len(genres) == 2


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_second_sync(session: AsyncSession) -> None:
    normalized = normalize_jikan_anime(SAMPLE)
    first = await upsert_anime_from_jikan(session, normalized)
    await session.commit()
    first_id = first.id

    second = await upsert_anime_from_jikan(session, normalized)
    await session.commit()

    assert second.id == first_id

    result = await session.execute(select(Anime).where(Anime.mal_id == 999))
    assert len(result.scalars().all()) == 1
