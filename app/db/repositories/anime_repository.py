"""
Anime repository: the only place that writes Anime/AnimeTitle/Genre/Studio
rows from normalized provider data, so upsert/dedup logic lives in one spot.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, AnimeGenre, AnimeStudio, AnimeTitle, Episode, Genre, Studio
from app.services.jikan_normalizer import NormalizedJikanAnime
from app.services.metadata_normalizer import NormalizedAnime


async def _get_or_create_genre(session: AsyncSession, name: str) -> Genre:
    result = await session.execute(select(Genre).where(Genre.name == name))
    genre = result.scalar_one_or_none()
    if genre is None:
        genre = Genre(name=name)
        session.add(genre)
        await session.flush()
    return genre


async def _get_or_create_studio(session: AsyncSession, anilist_id: int | None, name: str) -> Studio:
    studio: Studio | None = None
    if anilist_id is not None:
        result = await session.execute(select(Studio).where(Studio.anilist_id == anilist_id))
        studio = result.scalar_one_or_none()
    if studio is None:
        result = await session.execute(select(Studio).where(Studio.name == name))
        studio = result.scalar_one_or_none()
    if studio is None:
        studio = Studio(anilist_id=anilist_id, name=name)
        session.add(studio)
        await session.flush()
    elif anilist_id is not None and studio.anilist_id is None:
        studio.anilist_id = anilist_id  # backfill if we learn the ID later
    return studio


async def upsert_anime_from_anilist(session: AsyncSession, normalized: NormalizedAnime) -> Anime:
    result = await session.execute(select(Anime).where(Anime.anilist_id == normalized.anilist_id))
    anime = result.scalar_one_or_none()

    if anime is None:
        anime = Anime(anilist_id=normalized.anilist_id)
        session.add(anime)

    anime.mal_id = normalized.mal_id
    anime.title = normalized.title
    anime.english_title = normalized.english_title
    anime.native_title = normalized.native_title
    anime.romaji_title = normalized.romaji_title
    anime.synopsis = normalized.synopsis
    anime.poster_url = normalized.poster_url
    anime.banner_url = normalized.banner_url
    anime.trailer_url = normalized.trailer_url
    anime.format = normalized.format
    anime.status = normalized.status
    anime.season = normalized.season
    anime.season_year = normalized.season_year
    anime.episodes = normalized.episodes
    anime.duration_minutes = normalized.duration_minutes
    anime.source_material = normalized.source_material
    anime.score = normalized.score
    anime.popularity = normalized.popularity
    anime.rank = normalized.rank
    anime.favourites_count = normalized.favourites_count
    anime.country_of_origin = normalized.country_of_origin
    anime.last_synced_at = datetime.now(timezone.utc)

    await session.flush()  # ensures anime.id is populated for new rows

    await _sync_titles(session, anime, normalized)
    await _sync_genres(session, anime, normalized)
    await _sync_studios(session, anime, normalized)
    await _sync_episodes(session, anime, normalized)

    return anime


async def _sync_titles(session: AsyncSession, anime: Anime, normalized: NormalizedAnime) -> None:
    result = await session.execute(select(AnimeTitle).where(AnimeTitle.anime_id == anime.id))
    existing = {t.normalized_title for t in result.scalars().all()}

    for t in normalized.titles:
        if t.normalized_title in existing:
            continue
        session.add(
            AnimeTitle(
                anime_id=anime.id,
                title=t.title,
                title_type=t.title_type,
                normalized_title=t.normalized_title,
            )
        )


async def _sync_genres(session: AsyncSession, anime: Anime, normalized: NormalizedAnime) -> None:
    result = await session.execute(select(AnimeGenre).where(AnimeGenre.anime_id == anime.id))
    existing_genre_ids = {link.genre_id for link in result.scalars().all()}

    for name in normalized.genre_names:
        genre = await _get_or_create_genre(session, name)
        if genre.id not in existing_genre_ids:
            session.add(AnimeGenre(anime_id=anime.id, genre_id=genre.id))
            existing_genre_ids.add(genre.id)


async def _sync_studios(session: AsyncSession, anime: Anime, normalized: NormalizedAnime) -> None:
    result = await session.execute(select(AnimeStudio).where(AnimeStudio.anime_id == anime.id))
    existing_studio_ids = {link.studio_id for link in result.scalars().all()}

    for s in normalized.studios:
        studio = await _get_or_create_studio(session, s.anilist_id, s.name)
        if studio.id not in existing_studio_ids:
            session.add(AnimeStudio(anime_id=anime.id, studio_id=studio.id, role="studio"))
            existing_studio_ids.add(studio.id)


async def _sync_episodes(session: AsyncSession, anime: Anime, normalized: NormalizedAnime) -> None:
    if not normalized.episode_entries:
        return

    result = await session.execute(select(Episode).where(Episode.anime_id == anime.id))
    existing_by_number = {e.episode_number: e for e in result.scalars().all()}

    for entry in normalized.episode_entries:
        existing = existing_by_number.get(entry.episode_number)
        if existing is not None:
            existing.title = entry.title
            existing.thumbnail_url = entry.thumbnail_url
        else:
            session.add(
                Episode(
                    anime_id=anime.id,
                    episode_number=entry.episode_number,
                    title=entry.title,
                    thumbnail_url=entry.thumbnail_url,
                )
            )


async def get_genre_names(session: AsyncSession, anime_id: int) -> list[str]:
    result = await session.execute(select(AnimeGenre).where(AnimeGenre.anime_id == anime_id))
    return [link.genre.name for link in result.scalars().all()]


async def get_studio_names(session: AsyncSession, anime_id: int) -> list[str]:
    result = await session.execute(select(AnimeStudio).where(AnimeStudio.anime_id == anime_id))
    return [link.studio.name for link in result.scalars().all()]


async def upsert_anime_from_jikan(session: AsyncSession, normalized: NormalizedJikanAnime) -> Anime:
    """Fallback path used only when AniList search returns nothing for a
    query — dedups by mal_id rather than anilist_id since there's no
    AniList record to key on."""
    result = await session.execute(select(Anime).where(Anime.mal_id == normalized.mal_id))
    anime = result.scalar_one_or_none()

    if anime is None:
        anime = Anime(mal_id=normalized.mal_id)
        session.add(anime)

    anime.title = normalized.title
    anime.english_title = normalized.english_title
    anime.synopsis = normalized.synopsis
    anime.poster_url = normalized.poster_url
    anime.format = normalized.format
    anime.status = normalized.status
    anime.episodes = normalized.episodes
    anime.score = normalized.score
    anime.last_synced_at = datetime.now(timezone.utc)

    await session.flush()

    result = await session.execute(select(AnimeGenre).where(AnimeGenre.anime_id == anime.id))
    existing_genre_ids = {link.genre_id for link in result.scalars().all()}
    for name in normalized.genre_names:
        genre = await _get_or_create_genre(session, name)
        if genre.id not in existing_genre_ids:
            session.add(AnimeGenre(anime_id=anime.id, genre_id=genre.id))
            existing_genre_ids.add(genre.id)

    return anime