"""
Discovery browsing: trending, popular, top-rated, currently airing,
upcoming, seasonal, and genre listings. Unlike search, these are
inherently "what's current" queries, so they always hit AniList fresh
rather than trying a local-cache-first shortcut — but every result is
still upserted into the DB so opening a detail card afterward is
instant and fully cached (episodes/characters/staff etc. all still work
the same way they do for search results).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, AnimeGenre, Genre
from app.db.repositories.anime_repository import upsert_anime_from_anilist
from app.services.anilist_client import AniListClient, AniListError
from app.services.metadata_normalizer import normalize_anilist_media

logger = logging.getLogger(__name__)

# Maps an AniList `sort` value to the local column used for the
# cache-fallback ordering below. Only the sorts this module actually
# passes to _browse_and_upsert need an entry.
_LOCAL_SORT_COLUMN = {
    "TRENDING_DESC": Anime.popularity,
    "POPULARITY_DESC": Anime.popularity,
    "SCORE_DESC": Anime.score,
}

_SEASON_BY_MONTH = {
    12: "WINTER", 1: "WINTER", 2: "WINTER",
    3: "SPRING", 4: "SPRING", 5: "SPRING",
    6: "SUMMER", 7: "SUMMER", 8: "SUMMER",
    9: "FALL", 10: "FALL", 11: "FALL",
}

# AniList's standard genre list — stable for years; if it ever changes,
# AniList's GenreCollection query is the source of truth to re-check
# against (docs.anilist.co).
KNOWN_GENRES = [
    "Action", "Adventure", "Comedy", "Drama", "Ecchi", "Fantasy",
    "Hentai", "Horror", "Mahou Shoujo", "Mecha", "Music", "Mystery",
    "Psychological", "Romance", "Sci-Fi", "Slice of Life", "Sports",
    "Supernatural", "Thriller",
]


def get_current_season() -> tuple[str, int]:
    today = datetime.now(timezone.utc).date()
    season = _SEASON_BY_MONTH[today.month]
    year = today.year
    # December belongs to next year's WINTER season by AniList convention.
    if today.month == 12:
        year += 1
    return season, year


async def _local_browse_fallback(
    session: AsyncSession,
    *,
    sort: list[str],
    page: int,
    per_page: int,
    status: str | None = None,
    season: str | None = None,
    season_year: int | None = None,
    genres: list[str] | None = None,
) -> tuple[list[Anime], bool]:
    """Serves a browse listing from whatever's already cached locally,
    used when AniList itself is unreachable/erroring (rate limit, outage,
    etc.) so users still see something instead of a hard failure."""
    order_column = _LOCAL_SORT_COLUMN.get(sort[0] if sort else "", Anime.popularity)

    stmt = select(Anime).order_by(order_column.desc().nulls_last())
    if status is not None:
        stmt = stmt.where(Anime.status == status)
    if season is not None:
        stmt = stmt.where(Anime.season == season)
    if season_year is not None:
        stmt = stmt.where(Anime.season_year == season_year)
    if genres:
        stmt = stmt.join(AnimeGenre, AnimeGenre.anime_id == Anime.id).join(
            Genre, Genre.id == AnimeGenre.genre_id
        ).where(Genre.name.in_(genres))

    # Fetch one extra row to tell whether there's a next page, without
    # needing a separate COUNT query.
    offset = (page - 1) * per_page
    stmt = stmt.distinct().offset(offset).limit(per_page + 1)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_next_page = len(rows) > per_page
    return rows[:per_page], has_next_page


async def _browse_and_upsert(
    session: AsyncSession,
    client: AniListClient,
    *,
    sort: list[str],
    page: int,
    per_page: int,
    status: str | None = None,
    season: str | None = None,
    season_year: int | None = None,
    genres: list[str] | None = None,
) -> tuple[list[Anime], bool]:
    try:
        raw_page = await client.browse_anime(
            sort=sort,
            page=page,
            per_page=per_page,
            status=status,
            season=season,
            season_year=season_year,
            genres=genres,
        )
    except AniListError:
        # Degrade gracefully to cached data (e.g. during an AniList
        # outage or rate-limit) rather than a hard failure — same
        # approach as search_service's AniList-error handling.
        logger.exception(
            "anilist_browse_failed_falling_back_to_cache",
            extra={"sort": sort, "status": status, "season": season, "season_year": season_year, "genres": genres},
        )
        return await _local_browse_fallback(
            session,
            sort=sort,
            page=page,
            per_page=per_page,
            status=status,
            season=season,
            season_year=season_year,
            genres=genres,
        )

    media_list = raw_page.get("media") or []
    has_next_page = bool((raw_page.get("pageInfo") or {}).get("hasNextPage"))

    results: list[Anime] = []
    for media in media_list:
        try:
            normalized = normalize_anilist_media(media)
        except ValueError:
            continue
        anime = await upsert_anime_from_anilist(session, normalized)
        results.append(anime)

    return results, has_next_page


async def get_trending(session: AsyncSession, client: AniListClient, page: int = 1, per_page: int = 10):
    return await _browse_and_upsert(session, client, sort=["TRENDING_DESC"], page=page, per_page=per_page)


async def get_popular(session: AsyncSession, client: AniListClient, page: int = 1, per_page: int = 10):
    return await _browse_and_upsert(session, client, sort=["POPULARITY_DESC"], page=page, per_page=per_page)


async def get_top_rated(session: AsyncSession, client: AniListClient, page: int = 1, per_page: int = 10):
    return await _browse_and_upsert(session, client, sort=["SCORE_DESC"], page=page, per_page=per_page)


async def get_airing(session: AsyncSession, client: AniListClient, page: int = 1, per_page: int = 10):
    return await _browse_and_upsert(
        session, client, sort=["POPULARITY_DESC"], page=page, per_page=per_page, status="RELEASING"
    )


async def get_upcoming(session: AsyncSession, client: AniListClient, page: int = 1, per_page: int = 10):
    return await _browse_and_upsert(
        session, client, sort=["POPULARITY_DESC"], page=page, per_page=per_page, status="NOT_YET_RELEASED"
    )


async def get_seasonal(
    session: AsyncSession,
    client: AniListClient,
    season: str | None = None,
    season_year: int | None = None,
    page: int = 1,
    per_page: int = 10,
):
    if season is None or season_year is None:
        season, season_year = get_current_season()
    results, has_next = await _browse_and_upsert(
        session,
        client,
        sort=["POPULARITY_DESC"],
        page=page,
        per_page=per_page,
        season=season,
        season_year=season_year,
    )
    return results, has_next, season, season_year


async def get_by_genre(
    session: AsyncSession, client: AniListClient, genre: str, page: int = 1, per_page: int = 10
):
    return await _browse_and_upsert(
        session, client, sort=["POPULARITY_DESC"], page=page, per_page=per_page, genres=[genre]
    )
    
