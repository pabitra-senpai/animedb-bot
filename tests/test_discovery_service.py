from __future__ import annotations

from unittest.mock import patch
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.anilist_client import AniListClient
from app.services.discovery_service import (
    get_airing,
    get_by_genre,
    get_current_season,
    get_popular,
    get_seasonal,
    get_top_rated,
    get_trending,
    get_upcoming,
)
from tests.fixtures.anilist_samples import ONE_PIECE_MEDIA, search_page


def _client_with_transport(transport: httpx.MockTransport) -> AniListClient:
    return AniListClient(
        base_url="https://graphql.anilist.co",
        rate_limit_per_minute=1000,
        http_client=httpx.AsyncClient(transport=transport),
    )


def test_get_current_season_regular_month() -> None:
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 15, tzinfo=timezone.utc)

    with patch("app.services.discovery_service.datetime", _FixedDatetime):
        season, year = get_current_season()
    assert season == "SUMMER"
    assert year == 2026


def test_get_current_season_december_rolls_to_next_year_winter() -> None:
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 12, 20, tzinfo=timezone.utc)

    with patch("app.services.discovery_service.datetime", _FixedDatetime):
        season, year = get_current_season()
    assert season == "WINTER"
    assert year == 2027


@pytest.mark.asyncio
async def test_get_trending_upserts_results(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        results, has_next = await get_trending(session, client, page=1, per_page=10)
    finally:
        await client.close()

    assert len(results) == 1
    assert results[0].title == "One Piece"
    assert captured_variables["sort"] == ["TRENDING_DESC"]
    assert "status" not in captured_variables  # no status filter for trending


@pytest.mark.asyncio
async def test_get_airing_passes_status_filter(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_airing(session, client, page=1, per_page=10)
    finally:
        await client.close()

    assert captured_variables["status"] == "RELEASING"


@pytest.mark.asyncio
async def test_get_upcoming_passes_status_filter(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_upcoming(session, client, page=1, per_page=10)
    finally:
        await client.close()

    assert captured_variables["status"] == "NOT_YET_RELEASED"


@pytest.mark.asyncio
async def test_get_seasonal_defaults_to_current_season(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        results, has_next, season, year = await get_seasonal(session, client, page=1, per_page=10)
    finally:
        await client.close()

    assert season == captured_variables["season"]
    assert year == captured_variables["seasonYear"]


@pytest.mark.asyncio
async def test_get_seasonal_explicit_season(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        _, _, season, year = await get_seasonal(session, client, season="FALL", season_year=1999, page=1, per_page=10)
    finally:
        await client.close()

    assert season == "FALL"
    assert year == 1999
    assert captured_variables["season"] == "FALL"
    assert captured_variables["seasonYear"] == 1999


@pytest.mark.asyncio
async def test_get_by_genre_passes_genre_filter(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_by_genre(session, client, "Action", page=1, per_page=10)
    finally:
        await client.close()

    assert captured_variables["genre_in"] == ["Action"]


@pytest.mark.asyncio
async def test_has_next_page_reflected(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = search_page([ONE_PIECE_MEDIA])
        page["pageInfo"]["hasNextPage"] = True
        return httpx.Response(200, json={"data": {"Page": page}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        _, has_next = await get_popular(session, client, page=1, per_page=10)
    finally:
        await client.close()

    assert has_next is True


@pytest.mark.asyncio
async def test_get_top_rated_sort(session: AsyncSession) -> None:
    captured_variables = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_variables.update(json.loads(request.content)["variables"])
        return httpx.Response(200, json={"data": {"Page": search_page([ONE_PIECE_MEDIA])}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await get_top_rated(session, client, page=1, per_page=10)
    finally:
        await client.close()

    assert captured_variables["sort"] == ["SCORE_DESC"]
