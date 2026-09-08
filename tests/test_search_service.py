from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.anilist_client import AniListClient
from app.services.search_service import (
    InvalidSearchQueryError,
    search_anime,
    validate_and_normalize_query,
)
from tests.fixtures.anilist_samples import ONE_PIECE_MEDIA, search_page


def _client_with_transport(transport: httpx.MockTransport) -> AniListClient:
    return AniListClient(
        base_url="https://graphql.anilist.co",
        rate_limit_per_minute=1000,
        http_client=httpx.AsyncClient(transport=transport),
    )


def test_validate_and_normalize_query_rejects_empty() -> None:
    with pytest.raises(InvalidSearchQueryError):
        validate_and_normalize_query("")
    with pytest.raises(InvalidSearchQueryError):
        validate_and_normalize_query("   ")


def test_validate_and_normalize_query_rejects_too_long() -> None:
    with pytest.raises(InvalidSearchQueryError):
        validate_and_normalize_query("x" * 101)


def test_validate_and_normalize_query_normalizes_whitespace_and_case() -> None:
    assert validate_and_normalize_query("  One   PIECE  ") == "one piece"


@pytest.mark.asyncio
async def test_search_hits_anilist_when_cache_empty(session: AsyncSession) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        results = await search_anime(session, client, "One Piece")
        await session.commit()
    finally:
        await client.close()

    assert calls["count"] == 1
    assert len(results) == 1
    assert results[0].title == "One Piece"


@pytest.mark.asyncio
async def test_second_search_served_from_cache_without_hitting_anilist(session: AsyncSession) -> None:
    """First search populates the DB with 5+ matching titles; the second
    identical search should be answered from cache alone."""

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        # Return 5 distinct "One Piece"-titled entries so the cache
        # threshold (MIN_LOCAL_RESULTS_TO_SKIP_ANILIST) is met.
        media_list = []
        for i in range(5):
            m = dict(ONE_PIECE_MEDIA, id=21 + i, idMal=21 + i)
            m["title"] = {"romaji": f"One Piece {i}", "english": None, "native": None}
            media_list.append(m)
        return httpx.Response(200, json={"data": {"Page": search_page(media_list)}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await search_anime(session, client, "One Piece")
        await session.commit()

        results = await search_anime(session, client, "One Piece")
        await session.commit()
    finally:
        await client.close()

    assert calls["count"] == 1  # second search never reached AniList
    assert len(results) == 5


@pytest.mark.asyncio
async def test_anilist_failure_degrades_to_cached_results(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"errors": [{"message": "boom"}]})

    monkeypatch.setattr("app.services.anilist_client.asyncio.sleep", _no_sleep)

    client = _client_with_transport(httpx.MockTransport(failing_handler))
    try:
        # No local data and AniList unreachable -> empty results, no crash.
        results = await search_anime(session, client, "Nonexistent Show")
    finally:
        await client.close()

    assert results == []


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_falls_back_to_jikan_when_anilist_returns_nothing(session: AsyncSession) -> None:
    from app.services.jikan_client import JikanClient

    def anilist_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"Page": search_page([])}})

    def jikan_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "mal_id": 999,
                        "title": "Obscure Show",
                        "title_english": None,
                        "synopsis": "A show only Jikan knows about.",
                        "type": "TV",
                        "status": "Finished Airing",
                        "episodes": 12,
                        "score": 7.1,
                        "images": {"jpg": {"large_image_url": "https://example.com/obscure.jpg"}},
                        "genres": [{"name": "Drama"}],
                    }
                ]
            },
        )

    anilist_client = _client_with_transport(httpx.MockTransport(anilist_handler))
    jikan_client = JikanClient(rate_limit_per_minute=1000, http_client=httpx.AsyncClient(transport=httpx.MockTransport(jikan_handler)))
    try:
        results = await search_anime(session, anilist_client, "Obscure Show", jikan_client=jikan_client)
    finally:
        await anilist_client.close()
        await jikan_client.close()

    assert len(results) == 1
    assert results[0].title == "Obscure Show"
    assert results[0].mal_id == 999


@pytest.mark.asyncio
async def test_no_jikan_fallback_when_anilist_has_results(session: AsyncSession) -> None:
    from app.services.jikan_client import JikanClient

    jikan_calls = {"count": 0}

    def anilist_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    def jikan_handler(request: httpx.Request) -> httpx.Response:
        jikan_calls["count"] += 1
        return httpx.Response(200, json={"data": []})

    anilist_client = _client_with_transport(httpx.MockTransport(anilist_handler))
    jikan_client = JikanClient(rate_limit_per_minute=1000, http_client=httpx.AsyncClient(transport=httpx.MockTransport(jikan_handler)))
    try:
        await search_anime(session, anilist_client, "One Piece", jikan_client=jikan_client)
    finally:
        await anilist_client.close()
        await jikan_client.close()

    assert jikan_calls["count"] == 0  # AniList succeeded, Jikan never touched


@pytest.mark.asyncio
async def test_search_raises_for_invalid_query(session: AsyncSession) -> None:
    client = _client_with_transport(httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    try:
        with pytest.raises(InvalidSearchQueryError):
            await search_anime(session, client, "")
    finally:
        await client.close()
