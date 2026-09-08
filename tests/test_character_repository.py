from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.db.repositories.character_repository import (
    get_cached_character_count,
    get_cached_characters_page,
    get_voice_actor_names,
    upsert_character_edge,
)
from app.services.metadata_normalizer import normalize_characters_page
from tests.fixtures.anilist_samples import CHARACTERS_CONNECTION


@pytest.mark.asyncio
async def test_upsert_character_edges_creates_characters_and_va_links(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.flush()

    edges, _ = normalize_characters_page(CHARACTERS_CONNECTION)
    for edge in edges:
        await upsert_character_edge(session, anime.id, edge)
    await session.commit()

    count = await get_cached_character_count(session, anime.id)
    assert count == 2

    links = await get_cached_characters_page(session, anime.id, page=1, per_page=10)
    assert [l.character.name_full for l in links] == ["Monkey D. Luffy", "Nami"]
    assert [l.role for l in links] == ["MAIN", "SUPPORTING"]

    va_names = await get_voice_actor_names(session, anime.id, [l.character_id for l in links])
    assert va_names[links[0].character_id] == "Mayumi Tanaka"
    assert links[1].character_id not in va_names  # Nami has no voice actor in the fixture


@pytest.mark.asyncio
async def test_upsert_character_edge_is_idempotent(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.flush()

    edges, _ = normalize_characters_page(CHARACTERS_CONNECTION)
    for edge in edges:
        await upsert_character_edge(session, anime.id, edge)
    for edge in edges:  # simulate re-sync
        await upsert_character_edge(session, anime.id, edge)
    await session.commit()

    assert await get_cached_character_count(session, anime.id) == 2


@pytest.mark.asyncio
async def test_same_character_shared_across_two_anime(session: AsyncSession) -> None:
    anime1 = Anime(title="One Piece", anilist_id=21)
    anime2 = Anime(title="One Piece Movie", anilist_id=22)
    session.add_all([anime1, anime2])
    await session.flush()

    edges, _ = normalize_characters_page(CHARACTERS_CONNECTION)
    luffy_edge = edges[0]
    await upsert_character_edge(session, anime1.id, luffy_edge)
    await upsert_character_edge(session, anime2.id, luffy_edge)
    await session.commit()

    from sqlalchemy import select
    from app.db.models import Character

    result = await session.execute(select(Character).where(Character.anilist_id == 40))
    characters = result.scalars().all()
    assert len(characters) == 1  # not duplicated
