from __future__ import annotations

import httpx
import pytest

from app.services.jikan_client import JikanClient, JikanRateLimitError
from app.services.jikan_normalizer import normalize_jikan_anime

SAMPLE_JIKAN_ANIME = {
    "mal_id": 21,
    "title": "One Piece",
    "title_english": "One Piece",
    "synopsis": "Gol D. Roger was known as the Pirate King...",
    "type": "TV",
    "status": "Currently Airing",
    "episodes": None,
    "score": 8.72,
    "images": {"jpg": {"image_url": "https://example.com/small.jpg", "large_image_url": "https://example.com/large.jpg"}},
    "genres": [{"name": "Action"}, {"name": "Adventure"}],
    "explicit_genres": [],
}


def _client_with_transport(transport: httpx.MockTransport) -> JikanClient:
    return JikanClient(rate_limit_per_minute=1000, http_client=httpx.AsyncClient(transport=transport))


@pytest.mark.asyncio
async def test_search_anime_returns_data_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "q=One" in str(request.url)
        return httpx.Response(200, json={"data": [SAMPLE_JIKAN_ANIME]})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        results = await client.search_anime("One Piece")
    finally:
        await client.close()

    assert len(results) == 1
    assert results[0]["mal_id"] == 21


@pytest.mark.asyncio
async def test_get_anime_by_id_returns_none_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        result = await client.get_anime_by_id(999999999)
    finally:
        await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_rate_limit_exhausted_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        with pytest.raises(JikanRateLimitError):
            await client.search_anime("test")
    finally:
        await client.close()


def test_normalize_jikan_anime() -> None:
    normalized = normalize_jikan_anime(SAMPLE_JIKAN_ANIME)
    assert normalized.mal_id == 21
    assert normalized.title == "One Piece"
    assert normalized.poster_url == "https://example.com/large.jpg"
    assert normalized.status == "RELEASING"
    assert normalized.genre_names == ["Action", "Adventure"]
    assert normalized.score == 8.72


def test_normalize_jikan_anime_raises_without_title() -> None:
    with pytest.raises(ValueError):
        normalize_jikan_anime({"mal_id": 1, "title": None})


def test_normalize_jikan_anime_falls_back_to_small_image() -> None:
    data = dict(SAMPLE_JIKAN_ANIME, images={"jpg": {"image_url": "https://example.com/small.jpg"}})
    normalized = normalize_jikan_anime(data)
    assert normalized.poster_url == "https://example.com/small.jpg"
