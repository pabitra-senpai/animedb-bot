from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Anime
from app.db.session import get_session
from app.services.anilist_client import AniListClient
from app.services.sync_job import sync_stale_anime_once
from tests.fixtures.anilist_samples import ONE_PIECE_MEDIA

# Deliberately implausible AniList IDs so this test (which runs against
# the real app database via get_session(), not the isolated SQLite
# fixture) never collides with real anime IDs used elsewhere.
_STALE_TEST_ID = 900000021
_FRESH_TEST_ID = 900000099


def _client_with_transport(transport: httpx.MockTransport) -> AniListClient:
    return AniListClient(
        base_url="https://graphql.anilist.co",
        rate_limit_per_minute=1000,
        http_client=httpx.AsyncClient(transport=transport),
    )


async def _get_or_create(session, anilist_id: int, title: str, last_synced_at) -> Anime:
    result = await session.execute(select(Anime).where(Anime.anilist_id == anilist_id))
    anime = result.scalar_one_or_none()
    if anime is None:
        anime = Anime(title=title, anilist_id=anilist_id, last_synced_at=last_synced_at)
        session.add(anime)
    else:
        anime.last_synced_at = last_synced_at
    return anime


@pytest.mark.asyncio
async def test_sync_stale_anime_refreshes_old_rows_not_fresh_ones() -> None:
    # sync_job uses app.db.session.get_session directly (the real Postgres
    # session factory this test run's DATABASE_URL points at), so this
    # exercises the actual production code path rather than the SQLite
    # `session` fixture used elsewhere. Rerun-safe: upserts by anilist_id
    # instead of assuming a clean table.
    async with get_session() as session:
        await _get_or_create(
            session, _STALE_TEST_ID, "Sync Test Stale Anime",
            datetime.now(timezone.utc) - timedelta(days=2),
        )
        await _get_or_create(
            session, _FRESH_TEST_ID, "Sync Test Fresh Anime",
            datetime.now(timezone.utc),
        )

    call_log = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        anilist_id = body["variables"]["id"]
        call_log.append(anilist_id)
        if anilist_id == _STALE_TEST_ID:
            media = dict(ONE_PIECE_MEDIA, id=_STALE_TEST_ID, idMal=_STALE_TEST_ID)
            return httpx.Response(200, json={"data": {"Media": media}})
        return httpx.Response(200, json={"data": {"Media": None}})

    client = _client_with_transport(httpx.MockTransport(handler))
    try:
        synced, failed = await sync_stale_anime_once(client, ttl_seconds=3600, batch_size=50)
    finally:
        await client.close()

    assert _STALE_TEST_ID in call_log  # the stale one was refreshed
    assert _FRESH_TEST_ID not in call_log  # the fresh one was left alone

    async with get_session() as session:
        result = await session.execute(select(Anime).where(Anime.anilist_id == _STALE_TEST_ID))
        refreshed = result.scalar_one()
        assert refreshed.last_synced_at > datetime.now(timezone.utc) - timedelta(minutes=1)
