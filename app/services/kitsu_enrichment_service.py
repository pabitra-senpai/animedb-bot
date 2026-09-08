"""
On-demand episode enrichment from Kitsu: called only when AniList's own
episode data (streamingEpisodes) is sparse for the page being viewed.
Not part of the primary search/detail flow — this is deliberately an
opt-in, best-effort layer.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, Episode
from app.services.kitsu_client import KitsuClient, KitsuError
from app.services.kitsu_normalizer import find_best_kitsu_match, normalize_kitsu_episode
from app.utils.text import normalize_title

logger = logging.getLogger(__name__)


async def enrich_episodes_from_kitsu(
    session: AsyncSession, kitsu_client: KitsuClient, anime: Anime, limit: int = 20
) -> int:
    """Best-effort: resolves anime.kitsu_id (once, cached on the row from
    then on) and upserts whatever titled episodes Kitsu returns. Returns
    the number of episodes newly created or updated with a title."""
    if anime.kitsu_id is None:
        try:
            candidates = await kitsu_client.search_anime(anime.title, limit=5)
        except KitsuError:
            logger.warning("kitsu_search_failed", extra={"anime_id": anime.id})
            return 0

        kitsu_id = find_best_kitsu_match(candidates, normalize_title(anime.title))
        if kitsu_id is None or not str(kitsu_id).isdigit():
            return 0
        anime.kitsu_id = int(kitsu_id)

    try:
        episodes_raw = await kitsu_client.get_episodes(str(anime.kitsu_id), limit=limit)
    except KitsuError:
        logger.warning("kitsu_episodes_fetch_failed", extra={"anime_id": anime.id, "kitsu_id": anime.kitsu_id})
        return 0

    updated_count = 0
    for resource in episodes_raw:
        normalized = normalize_kitsu_episode(resource)
        if normalized is None or not normalized.title:
            continue

        result = await session.execute(
            select(Episode).where(
                Episode.anime_id == anime.id, Episode.episode_number == normalized.episode_number
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if not existing.title:
                existing.title = normalized.title
                existing.thumbnail_url = existing.thumbnail_url or normalized.thumbnail_url
                updated_count += 1
        else:
            session.add(
                Episode(
                    anime_id=anime.id,
                    episode_number=normalized.episode_number,
                    title=normalized.title,
                    thumbnail_url=normalized.thumbnail_url,
                )
            )
            updated_count += 1

    return updated_count

