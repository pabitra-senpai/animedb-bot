from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.db.repositories.staff_repository import (
    get_cached_staff_count,
    get_cached_staff_page,
    upsert_staff_edge,
)
from app.services.metadata_normalizer import normalize_staff_page
from tests.fixtures.anilist_samples import STAFF_CONNECTION


@pytest.mark.asyncio
async def test_upsert_staff_edges(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.flush()

    edges, _ = normalize_staff_page(STAFF_CONNECTION)
    for edge in edges:
        await upsert_staff_edge(session, anime.id, edge)
    await session.commit()

    assert await get_cached_staff_count(session, anime.id) == 2
    links = await get_cached_staff_page(session, anime.id, page=1, per_page=10)
    assert [l.staff.name_full for l in links] == ["Konosuke Uda", "Eiichiro Oda"]
    assert [l.role for l in links] == ["Director", "Original Creator"]


@pytest.mark.asyncio
async def test_upsert_staff_edge_is_idempotent(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.flush()

    edges, _ = normalize_staff_page(STAFF_CONNECTION)
    for edge in edges:
        await upsert_staff_edge(session, anime.id, edge)
    for edge in edges:
        await upsert_staff_edge(session, anime.id, edge)
    await session.commit()

    assert await get_cached_staff_count(session, anime.id) == 2


@pytest.mark.asyncio
async def test_same_person_can_hold_two_roles_on_same_anime(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.flush()

    edges, _ = normalize_staff_page(STAFF_CONNECTION)
    oda = edges[1]
    await upsert_staff_edge(session, anime.id, oda)

    from dataclasses import replace

    oda_as_writer = replace(oda, role="Writer")
    await upsert_staff_edge(session, anime.id, oda_as_writer)
    await session.commit()

    # Same person (staff.anilist_id), two distinct role credits.
    assert await get_cached_staff_count(session, anime.id) == 2
    from sqlalchemy import select
    from app.db.models import Staff

    result = await session.execute(select(Staff).where(Staff.anilist_id == 501))
    assert len(result.scalars().all()) == 1
