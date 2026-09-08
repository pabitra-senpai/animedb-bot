"""
Orchestrates character listing: page 1 is served from the DB cache when
anything is already cached for the anime; any other page (or a cold
cache) fetches that page from AniList and upserts it, mirroring the
pattern established in search_service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.db.repositories.character_repository import (
    get_cached_character_count,
    get_cached_characters_page,
    get_voice_actor_names,
    upsert_character_edge,
)
from app.services.anilist_client import AniListClient, AniListError
from app.services.metadata_normalizer import normalize_characters_page

logger = logging.getLogger(__name__)


@dataclass
class CharacterDisplay:
    name: str
    role: str
    voice_actor_name: str | None


async def get_anime_characters_page(
    session: AsyncSession,
    client: AniListClient,
    anime: Anime,
    page: int = 1,
    per_page: int = 10,
) -> tuple[list[CharacterDisplay], bool]:
    if anime.anilist_id is None:
        links = await get_cached_characters_page(session, anime.id, page, per_page)
        return await _to_display(session, anime.id, links), False

    if page == 1:
        cached_count = await get_cached_character_count(session, anime.id)
        if cached_count > 0:
            links = await get_cached_characters_page(session, anime.id, page, per_page)
            return await _to_display(session, anime.id, links), cached_count > per_page

    try:
        raw = await client.get_anime_characters(anime.anilist_id, page=page, per_page=per_page)
    except AniListError:
        logger.exception("anilist_characters_fetch_failed", extra={"anime_id": anime.id, "page": page})
        links = await get_cached_characters_page(session, anime.id, page, per_page)
        return await _to_display(session, anime.id, links), False

    edges, has_next_page = normalize_characters_page(raw)
    for edge in edges:
        await upsert_character_edge(session, anime.id, edge)

    links = await get_cached_characters_page(session, anime.id, page, per_page)
    return await _to_display(session, anime.id, links), has_next_page


async def _to_display(session: AsyncSession, anime_id: int, links) -> list[CharacterDisplay]:
    character_ids = [link.character_id for link in links]
    va_names = await get_voice_actor_names(session, anime_id, character_ids)
    return [
        CharacterDisplay(
            name=link.character.name_full,
            role=link.role,
            voice_actor_name=va_names.get(link.character_id),
        )
        for link in links
    ]
