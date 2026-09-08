"""
Periodic background sync: finds Anime rows whose AniList data is stale
(per cache_service's TTL policy) and refreshes them, oldest first. Runs
as a plain asyncio loop alongside the bot's polling task — no extra
scheduler dependency needed for a single-instance deployment.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.db.models import Anime
from app.db.repositories.anime_repository import upsert_anime_from_anilist
from app.db.session import get_session
from app.services.anilist_client import AniListClient, AniListError
from app.services.cache_service import is_stale
from app.services.metadata_normalizer import normalize_anilist_media

logger = logging.getLogger(__name__)


async def sync_stale_anime_once(
    client: AniListClient, ttl_seconds: int, batch_size: int
) -> tuple[int, int]:
    """Runs a single sync pass. Returns (synced_count, failed_count)."""
    synced = 0
    failed = 0

    async with get_session() as session:
        # Anime never synced (last_synced_at is NULL) or oldest-synced first.
        result = await session.execute(
            select(Anime)
            .where(Anime.anilist_id.is_not(None))
            .order_by(Anime.last_synced_at.asc().nulls_first())
            .limit(batch_size * 3)  # over-fetch since is_stale() filters further
        )
        candidates = [a for a in result.scalars().all() if is_stale(a, ttl_seconds)][:batch_size]

        for anime in candidates:
            try:
                media = await client.get_anime_by_id(anime.anilist_id)
            except AniListError:
                logger.warning("background_sync_anime_failed", extra={"anime_id": anime.id, "anilist_id": anime.anilist_id})
                failed += 1
                continue

            if media is None:
                failed += 1
                continue

            try:
                normalized = normalize_anilist_media(media)
            except ValueError:
                failed += 1
                continue

            await upsert_anime_from_anilist(session, normalized)
            synced += 1

    if synced or failed:
        logger.info("background_sync_pass_complete", extra={"synced": synced, "failed": failed})

    return synced, failed


async def run_periodic_sync(
    client: AniListClient, interval_seconds: int, ttl_seconds: int, batch_size: int
) -> None:
    """Runs forever until cancelled. Intended to be wrapped in
    asyncio.create_task() alongside the bot's polling task."""
    logger.info(
        "background_sync_started",
        extra={"interval_seconds": interval_seconds, "ttl_seconds": ttl_seconds, "batch_size": batch_size},
    )
    while True:
        try:
            await sync_stale_anime_once(client, ttl_seconds, batch_size)
        except Exception:
            logger.exception("background_sync_pass_crashed")
        await asyncio.sleep(interval_seconds)
