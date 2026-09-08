from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, Episode
from app.services.episode_service import get_episode_page


@pytest.mark.asyncio
async def test_episode_page_with_known_total_and_no_synced_data(session: AsyncSession) -> None:
    anime = Anime(title="Frieren", episodes=28)
    session.add(anime)
    await session.commit()

    page1, has_next = await get_episode_page(session, anime, page=1, per_page=10)
    assert [e.number for e in page1] == list(range(1, 11))
    assert all(e.title is None for e in page1)
    assert has_next is True

    page3, has_next3 = await get_episode_page(session, anime, page=3, per_page=10)
    assert [e.number for e in page3] == [21, 22, 23, 24, 25, 26, 27, 28]
    assert has_next3 is False


@pytest.mark.asyncio
async def test_episode_page_beyond_total_returns_empty(session: AsyncSession) -> None:
    anime = Anime(title="Frieren", episodes=28)
    session.add(anime)
    await session.commit()

    page, has_next = await get_episode_page(session, anime, page=5, per_page=10)
    assert page == []
    assert has_next is False


@pytest.mark.asyncio
async def test_episode_page_overlays_real_synced_data(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", episodes=1000)
    session.add(anime)
    await session.flush()
    session.add(Episode(anime_id=anime.id, episode_number=1, title="Romance Dawn", air_date=date(1999, 10, 20)))
    await session.commit()

    page, _ = await get_episode_page(session, anime, page=1, per_page=10)
    ep1 = next(e for e in page if e.number == 1)
    assert ep1.title == "Romance Dawn"
    assert ep1.air_date == date(1999, 10, 20)

    ep2 = next(e for e in page if e.number == 2)
    assert ep2.title is None  # not synced, still listed


@pytest.mark.asyncio
async def test_episode_page_with_unknown_total_shows_only_synced_episodes(session: AsyncSession) -> None:
    anime = Anime(title="Ongoing Show", episodes=None)
    session.add(anime)
    await session.flush()
    session.add(Episode(anime_id=anime.id, episode_number=1, title="First"))
    session.add(Episode(anime_id=anime.id, episode_number=2, title="Second"))
    await session.commit()

    page, has_next = await get_episode_page(session, anime, page=1, per_page=10)
    assert [e.number for e in page] == [1, 2]
    assert has_next is False


@pytest.mark.asyncio
async def test_episode_page_with_unknown_total_and_no_data_returns_empty(session: AsyncSession) -> None:
    anime = Anime(title="No Data Show", episodes=None)
    session.add(anime)
    await session.commit()

    page, has_next = await get_episode_page(session, anime, page=1, per_page=10)
    assert page == []
    assert has_next is False
