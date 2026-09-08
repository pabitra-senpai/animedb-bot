from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.services.anilist_client import AniListClient
from app.services.staff_service import get_anime_staff_page
from tests.fixtures.anilist_samples import STAFF_CONNECTION


def _client_with_transport(transport: httpx.MockTransport) -> AniListClient:
    return AniListClient(
        base_url="https://graphql.anilist.co",
        rate_limit_per_minute=1000,
        http_client=httpx.AsyncClient(transport=transport),
    )


@pytest.mark.asyncio
async def test_first_call_fetches_from_anilist(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.commit()

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"data": {"Media": {"staff": STAFF_CONNECTION}}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        staff, has_next = await get_anime_staff_page(session, client, anime, page=1, per_page=10)
    finally:
        await client.close()

    assert calls["count"] == 1
    assert [s.name for s in staff] == ["Konosuke Uda", "Eiichiro Oda"]
    assert has_next is False


@pytest.mark.asyncio
async def test_second_call_served_from_cache(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.commit()

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"data": {"Media": {"staff": STAFF_CONNECTION}}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_anime_staff_page(session, client, anime, page=1, per_page=10)
        await session.commit()
        await get_anime_staff_page(session, client, anime, page=1, per_page=10)
    finally:
        await client.close()

    assert calls["count"] == 1
