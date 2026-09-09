"""
Search orchestration: validate -> local DB search -> AniList fallback ->
upsert -> return. Follows the SEARCH WORKFLOW from the project spec:
don't call AniList when the local cache already answers the query well.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, AnimeTitle
from app.db.repositories.anime_repository import upsert_anime_from_anilist, upsert_anime_from_jikan
from app.services.anilist_client import AniListClient, AniListError
from app.services.jikan_client import JikanClient, JikanError
from app.services.jikan_normalizer import normalize_jikan_anime
from app.services.metadata_normalizer import normalize_anilist_media
from app.utils.text import normalize_title

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 100
MIN_LOCAL_RESULTS_TO_SKIP_ANILIST = 5


class InvalidSearchQueryError(ValueError):
    """Raised for empty/too-long/whitespace-only queries."""


def validate_and_normalize_query(raw_query: str) -> str:
    if raw_query is None:
        raise InvalidSearchQueryError("Search query cannot be empty.")

    normalized = normalize_title(raw_query)
    if not normalized:
        raise InvalidSearchQueryError("Search query cannot be empty.")
    if len(raw_query) > MAX_QUERY_LENGTH:
        raise InvalidSearchQueryError(
            f"Search query is too long (max {MAX_QUERY_LENGTH} characters)."
        )
    return normalized


async def _search_local(session: AsyncSession, normalized_query: str, limit: int) -> list[Anime]:
    stmt = (
        select(Anime)
        .join(AnimeTitle, AnimeTitle.anime_id == Anime.id)
        .where(AnimeTitle.normalized_title.contains(normalized_query))
        .order_by(Anime.popularity.desc().nulls_last())
        .limit(limit)
        .distinct()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_anime(
    session: AsyncSession,
    client: AniListClient,
    raw_query: str,
    page: int = 1,
    per_page: int = 10,
    jikan_client: JikanClient | None = None,
) -> list[Anime]:
    normalized_query = validate_and_normalize_query(raw_query)

    logger.info("anime_search", extra={"query": normalized_query, "page": page})

    local_results = await _search_local(session, normalized_query, per_page)
    if len(local_results) >= MIN_LOCAL_RESULTS_TO_SKIP_ANILIST and page == 1:
        logger.info(
            "anime_search_served_from_cache",
            extra={"query": normalized_query, "result_count": len(local_results)},
        )
        return local_results

    results: list[Anime] = []

    try:
        anilist_page = await client.search_anime(raw_query.strip(), page=page, per_page=per_page)
    except AniListError:
        logger.exception(
            "anilist_search_failed_falling_back_to_jikan_then_cache",
            extra={"query": normalized_query},
        )
        anilist_page = None

    if anilist_page is not None:
        media_list = anilist_page.get("media") or []
        for media in media_list:
            try:
                normalized = normalize_anilist_media(media)
            except ValueError:
                logger.warning("skipping_media_without_title", extra={"anilist_id": media.get("id")})
                continue
            anime = await upsert_anime_from_anilist(session, normalized)
            results.append(anime)

    # AniList found nothing for this query (or errored out) — try Jikan
    # (MyAnimeList mirror) as a secondary source before giving up. Only on
    # page 1: Jikan is a fallback for "AniList has no results at all", not
    # a second page source for an already-successful AniList search.
    if not results and jikan_client is not None and page == 1:
        results = await _search_jikan_fallback(session, jikan_client, raw_query.strip(), per_page)

    # AniList errored AND Jikan found nothing either (or wasn't available)
    # — degrade gracefully to whatever's cached locally rather than a hard
    # failure, per the project's error-handling requirements.
    if not results and anilist_page is None:
        results = local_results

    return results


async def _search_jikan_fallback(
    session: AsyncSession, jikan_client: JikanClient, query: str, limit: int
) -> list[Anime]:
    try:
        jikan_results = await jikan_client.search_anime(query, limit=limit)
    except JikanError:
        logger.exception("jikan_fallback_search_failed", extra={"query": query})
        return []

    results: list[Anime] = []
    for data in jikan_results:
        try:
            normalized = normalize_jikan_anime(data)
        except ValueError:
            continue
        anime = await upsert_anime_from_jikan(session, normalized)
        results.append(anime)

    if results:
        logger.info("anime_search_served_from_jikan_fallback", extra={"query": query, "result_count": len(results)})

    return results
    
