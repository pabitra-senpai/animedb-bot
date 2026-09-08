from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.services.anilist_client import AniListClient
from app.services.character_service import get_anime_characters_page
from tests.fixtures.anilist_samples import CHARACTERS_CONNECTION


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
        return httpx.Response(200, json={"data": {"Media": {"characters": CHARACTERS_CONNECTION}}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        characters, has_next = await get_anime_characters_page(session, client, anime, page=1, per_page=10)
    finally:
        await client.close()

    assert calls["count"] == 1
    assert len(characters) == 2
    assert characters[0].name == "Monkey D. Luffy"
    assert characters[0].voice_actor_name == "Mayumi Tanaka"
    assert has_next is True


@pytest.mark.asyncio
async def test_second_page_one_call_served_from_cache(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.commit()

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"data": {"Media": {"characters": CHARACTERS_CONNECTION}}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_anime_characters_page(session, client, anime, page=1, per_page=10)
        await session.commit()
        await get_anime_characters_page(session, client, anime, page=1, per_page=10)
    finally:
        await client.close()

    assert calls["count"] == 1  # second call never reached AniList


@pytest.mark.asyncio
async def test_page_two_always_fetches_fresh(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.commit()

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"data": {"Media": {"characters": CHARACTERS_CONNECTION}}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_anime_characters_page(session, client, anime, page=1, per_page=10)
        await session.commit()
        await get_anime_characters_page(session, client, anime, page=2, per_page=10)
    finally:
        await client.close()

    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_anilist_failure_falls_back_to_whatever_is_cached(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    anime = Anime(title="One Piece", anilist_id=21)
    session.add(anime)
    await session.commit()

    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"errors": [{"message": "boom"}]})

    monkeypatch.setattr("app.services.anilist_client.asyncio.sleep", _no_sleep)

    client = _client_with_transport(httpx.MockTransport(failing_handler))
    try:
        characters, has_next = await get_anime_characters_page(session, client, anime, page=1, per_page=10)
    finally:
        await client.close()

    assert characters == []
    assert has_next is False


async def _no_sleep(_seconds: float) -> None:
    return None
