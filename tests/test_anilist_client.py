from __future__ import annotations

import httpx
import pytest

from app.services.anilist_client import (
    AniListClient,
    AniListError,
    AniListRateLimitError,
    AniListUnavailableError,
)
from tests.fixtures.anilist_samples import ONE_PIECE_MEDIA, search_page


def _client_with_transport(transport: httpx.MockTransport) -> AniListClient:
    http_client = httpx.AsyncClient(transport=transport)
    return AniListClient(
        base_url="https://graphql.anilist.co",
        rate_limit_per_minute=1000,  # don't self-throttle during tests
        http_client=http_client,
    )


@pytest.mark.asyncio
async def test_search_anime_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        page = await client.search_anime("One Piece")
        assert page["media"][0]["id"] == 21
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_retries_then_succeeds_after_429() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"errors": [{"message": "Too Many Requests.", "status": 429}]},
            )
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        page = await client.search_anime("One Piece")
        assert calls["count"] == 2
        assert page["media"][0]["id"] == 21
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_raises_rate_limit_error_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "0"},
            json={"errors": [{"message": "Too Many Requests.", "status": 429}]},
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(AniListRateLimitError):
            await client.search_anime("One Piece")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_outage_raises_unavailable_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "errors": [
                    {
                        "message": "The AniList API has been temporarily disabled due to severe stability issues.",
                        "status": 403,
                    }
                ],
                "data": None,
            },
        )

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(AniListUnavailableError):
            await client.search_anime("One Piece")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_graphql_error_with_200_status_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": None, "errors": [{"message": "Invalid variables"}]})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(AniListError):
            await client.search_anime("")
    finally:
        await client.close()


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_transient_transport_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    # Avoid actually sleeping through the exponential backoff in tests.
    monkeypatch.setattr("app.services.anilist_client.asyncio.sleep", _no_sleep)
    try:
        page = await client.search_anime("One Piece")
        assert calls["count"] == 2
        assert page["media"][0]["id"] == 21
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_get_anime_by_id_returns_none_when_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"Media": None}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        media = await client.get_anime_by_id(99999999)
        assert media is None
    finally:
        await client.close()
