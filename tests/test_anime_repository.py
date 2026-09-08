from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnimeGenre, AnimeStudio, AnimeTitle, Studio
from app.db.repositories.anime_repository import upsert_anime_from_anilist
from app.services.metadata_normalizer import normalize_anilist_media
from tests.fixtures.anilist_samples import MINIMAL_MEDIA, ONE_PIECE_MEDIA


@pytest.mark.asyncio
async def test_upsert_creates_anime_with_titles_genres_studios(session: AsyncSession) -> None:
    normalized = normalize_anilist_media(ONE_PIECE_MEDIA)
    anime = await upsert_anime_from_anilist(session, normalized)
    await session.commit()

    assert anime.id is not None
    assert anime.anilist_id == 21
    assert anime.last_synced_at is not None

    titles = (await session.execute(select(AnimeTitle).where(AnimeTitle.anime_id == anime.id))).scalars().all()
    genres = (await session.execute(select(AnimeGenre).where(AnimeGenre.anime_id == anime.id))).scalars().all()
    studios = (await session.execute(select(AnimeStudio).where(AnimeStudio.anime_id == anime.id))).scalars().all()

    assert len(titles) == 3  # romaji, native, synonym (english == romaji, deduped)
    assert len(genres) == 3
    assert len(studios) == 1


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_second_sync(session: AsyncSession) -> None:
    normalized = normalize_anilist_media(ONE_PIECE_MEDIA)
    first = await upsert_anime_from_anilist(session, normalized)
    await session.commit()
    first_id = first.id

    # Simulate a resync (e.g. background refresh job) with identical data.
    second = await upsert_anime_from_anilist(session, normalized)
    await session.commit()

    assert second.id == first_id  # same row updated, not duplicated

    titles = (await session.execute(select(AnimeTitle).where(AnimeTitle.anime_id == first_id))).scalars().all()
    assert len(titles) == 3  # no duplicate titles created on resync


@pytest.mark.asyncio
async def test_upsert_updates_changed_fields_on_resync(session: AsyncSession) -> None:
    normalized = normalize_anilist_media(ONE_PIECE_MEDIA)
    anime = await upsert_anime_from_anilist(session, normalized)
    await session.commit()

    updated_media = dict(ONE_PIECE_MEDIA, averageScore=90, popularity=600000)
    updated_normalized = normalize_anilist_media(updated_media)
    anime = await upsert_anime_from_anilist(session, updated_normalized)
    await session.commit()

    assert anime.score == 9.0
    assert anime.popularity == 600000


@pytest.mark.asyncio
async def test_shared_studio_reused_across_anime(session: AsyncSession) -> None:
    op = normalize_anilist_media(ONE_PIECE_MEDIA)
    await upsert_anime_from_anilist(session, op)

    # Second anime, different AniList ID, same studio (Toei, id=18).
    other_media = dict(
        MINIMAL_MEDIA,
        id=555,
        studios={"nodes": [{"id": 18, "name": "Toei Animation"}]},
    )
    other = normalize_anilist_media(other_media)
    await upsert_anime_from_anilist(session, other)
    await session.commit()

    studios = (await session.execute(select(Studio).where(Studio.anilist_id == 18))).scalars().all()
    assert len(studios) == 1  # not duplicated
