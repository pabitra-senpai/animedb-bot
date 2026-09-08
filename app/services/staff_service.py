"""
Orchestrates staff listing, mirroring character_service's cache-first
page-1 / fetch-on-demand pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.db.repositories.staff_repository import (
    get_cached_staff_count,
    get_cached_staff_page,
    upsert_staff_edge,
)
from app.services.anilist_client import AniListClient, AniListError
from app.services.metadata_normalizer import normalize_staff_page

logger = logging.getLogger(__name__)


@dataclass
class StaffDisplay:
    name: str
    role: str


async def get_anime_staff_page(
    session: AsyncSession,
    client: AniListClient,
    anime: Anime,
    page: int = 1,
    per_page: int = 10,
) -> tuple[list[StaffDisplay], bool]:
    if anime.anilist_id is None:
        links = await get_cached_staff_page(session, anime.id, page, per_page)
        return [StaffDisplay(name=l.staff.name_full, role=l.role) for l in links], False

    if page == 1:
        cached_count = await get_cached_staff_count(session, anime.id)
        if cached_count > 0:
            links = await get_cached_staff_page(session, anime.id, page, per_page)
            return (
                [StaffDisplay(name=l.staff.name_full, role=l.role) for l in links],
                cached_count > per_page,
            )

    try:
        raw = await client.get_anime_staff(anime.anilist_id, page=page, per_page=per_page)
    except AniListError:
        logger.exception("anilist_staff_fetch_failed", extra={"anime_id": anime.id, "page": page})
        links = await get_cached_staff_page(session, anime.id, page, per_page)
        return [StaffDisplay(name=l.staff.name_full, role=l.role) for l in links], False

    edges, has_next_page = normalize_staff_page(raw)
    for edge in edges:
        await upsert_staff_edge(session, anime.id, edge)

    links = await get_cached_staff_page(session, anime.id, page, per_page)
    return [StaffDisplay(name=l.staff.name_full, role=l.role) for l in links], has_next_page
