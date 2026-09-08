from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, Episode
from app.services.kitsu_client import KitsuClient
from app.services.kitsu_enrichment_service import enrich_episodes_from_kitsu
from app.services.kitsu_normalizer import find_best_kitsu_match, normalize_kitsu_episode

SAMPLE_SEARCH_RESULTS = [
    {"id": "12", "attributes": {"canonicalTitle": "One Piece", "titles": {"en": "One Piece", "en_jp": "One Piece"}}}
]

SAMPLE_EPISODE = {
    "attributes": {
        "number": 1,
        "canonicalTitle": "Romance Dawn, the Great Swordsman!",
        "thumbnail": {"original": "https://example.com/ep1.jpg"},
    }
}


def _client_with_transport(transport: httpx.MockTransport) -> KitsuClient:
    return KitsuClient(rate_limit_per_minute=1000, http_client=httpx.AsyncClient(transport=transport))


@pytest.mark.asyncio
async def test_search_anime_returns_data_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": SAMPLE_SEARCH_RESULTS})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        results = await client.search_anime("One Piece")
    finally:
        await client.close()

    assert len(results) == 1
    assert results[0]["id"] == "12"


@pytest.mark.asyncio
async def test_get_episodes_returns_data_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [SAMPLE_EPISODE]})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        episodes = await client.get_episodes("12")
    finally:
        await client.close()

    assert len(episodes) == 1


def test_normalize_kitsu_episode() -> None:
    normalized = normalize_kitsu_episode(SAMPLE_EPISODE)
    assert normalized.episode_number == 1
    assert normalized.title == "Romance Dawn, the Great Swordsman!"
    assert normalized.thumbnail_url == "https://example.com/ep1.jpg"


def test_normalize_kitsu_episode_returns_none_without_number() -> None:
    assert normalize_kitsu_episode({"attributes": {"canonicalTitle": "X"}}) is None


def test_find_best_kitsu_match_single_result() -> None:
    match = find_best_kitsu_match(SAMPLE_SEARCH_RESULTS, "something else entirely")
    assert match == "12"  # sole result accepted even without exact title match


def test_find_best_kitsu_match_exact_title_among_multiple() -> None:
    results = [
        {"id": "1", "attributes": {"canonicalTitle": "Naruto", "titles": {}}},
        {"id": "12", "attributes": {"canonicalTitle": "One Piece", "titles": {"en": "One Piece"}}},
    ]
    match = find_best_kitsu_match(results, "one piece")
    assert match == "12"


def test_find_best_kitsu_match_no_confident_match() -> None:
    results = [
        {"id": "1", "attributes": {"canonicalTitle": "Naruto", "titles": {}}},
        {"id": "2", "attributes": {"canonicalTitle": "Bleach", "titles": {}}},
    ]
    match = find_best_kitsu_match(results, "one piece")
    assert match is None


def test_find_best_kitsu_match_empty_results() -> None:
    assert find_best_kitsu_match([], "anything") is None


@pytest.mark.asyncio
async def test_enrich_episodes_resolves_kitsu_id_and_upserts(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", kitsu_id=None)
    session.add(anime)
    await session.flush()

    def handler(request: httpx.Request) -> httpx.Response:
        if "/anime/12/episodes" in str(request.url):
            return httpx.Response(200, json={"data": [SAMPLE_EPISODE]})
        return httpx.Response(200, json={"data": SAMPLE_SEARCH_RESULTS})

    kitsu_client = _client_with_transport(httpx.MockTransport(handler))
    try:
        count = await enrich_episodes_from_kitsu(session, kitsu_client, anime)
        await session.commit()
    finally:
        await kitsu_client.close()

    assert count == 1
    assert anime.kitsu_id == 12

    result = await session.execute(select(Episode).where(Episode.anime_id == anime.id))
    episodes = result.scalars().all()
    assert len(episodes) == 1
    assert episodes[0].title == "Romance Dawn, the Great Swordsman!"


@pytest.mark.asyncio
async def test_enrich_episodes_skips_when_no_confident_match(session: AsyncSession) -> None:
    anime = Anime(title="Some Obscure Show", kitsu_id=None)
    session.add(anime)
    await session.flush()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "1", "attributes": {"canonicalTitle": "Naruto", "titles": {}}},
                    {"id": "2", "attributes": {"canonicalTitle": "Bleach", "titles": {}}},
                ]
            },
        )

    kitsu_client = _client_with_transport(httpx.MockTransport(handler))
    try:
        count = await enrich_episodes_from_kitsu(session, kitsu_client, anime)
    finally:
        await kitsu_client.close()

    assert count == 0
    assert anime.kitsu_id is None


@pytest.mark.asyncio
async def test_enrich_episodes_skips_kitsu_search_when_id_already_known(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", kitsu_id=12)
    session.add(anime)
    await session.flush()

    search_called = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "filter" in str(request.url):
            search_called["count"] += 1
            return httpx.Response(200, json={"data": SAMPLE_SEARCH_RESULTS})
        return httpx.Response(200, json={"data": [SAMPLE_EPISODE]})

    kitsu_client = _client_with_transport(httpx.MockTransport(handler))
    try:
        await enrich_episodes_from_kitsu(session, kitsu_client, anime)
    finally:
        await kitsu_client.close()

    assert search_called["count"] == 0  # kitsu_id already known -> no search needed


@pytest.mark.asyncio
async def test_enrich_episodes_does_not_overwrite_existing_title(session: AsyncSession) -> None:
    anime = Anime(title="One Piece", kitsu_id=12)
    session.add(anime)
    await session.flush()
    session.add(Episode(anime_id=anime.id, episode_number=1, title="Already Titled From AniList"))
    await session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [SAMPLE_EPISODE]})

    kitsu_client = _client_with_transport(httpx.MockTransport(handler))
    try:
        count = await enrich_episodes_from_kitsu(session, kitsu_client, anime)
        await session.commit()
    finally:
        await kitsu_client.close()

    assert count == 0  # existing title preserved, not counted as an update

    result = await session.execute(select(Episode).where(Episode.anime_id == anime.id))
    ep = result.scalar_one()
    assert ep.title == "Already Titled From AniList"
