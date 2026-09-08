"""
Kitsu client, JSON:API format.

Verified against current docs/community sources as of this writing:
- Base URL https://kitsu.io/api/edge, public GET reads need no API key.
- Search: GET /anime?filter[text]=<query>
- Episodes: GET /anime/{kitsu_id}/episodes
- Rate limit is informally cited around 100 req/hour for fair use on the
  public tier — this client defaults very conservatively since episode
  enrichment is an optional nice-to-have, not a critical path. Re-verify
  at https://kitsu.docs.apiary.io before raising the default.

Used only for on-demand episode-title enrichment (episode_service /
anime_extras.py) — not part of the primary search/detail flow.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

import httpx

logger = logging.getLogger(__name__)


class KitsuError(Exception):
    pass


class _RateLimiter:
    def __init__(self, max_per_minute: int) -> None:
        self._max = max_per_minute
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            while self._timestamps and now - self._timestamps[0] > 60:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max:
                wait_for = 60 - (now - self._timestamps[0])
                if wait_for > 0:
                    logger.info("kitsu_rate_limit_self_throttle", extra={"wait_seconds": round(wait_for, 2)})
                    await asyncio.sleep(wait_for)
            self._timestamps.append(time.monotonic())


class KitsuClient:
    def __init__(
        self,
        base_url: str = "https://kitsu.io/api/edge",
        rate_limit_per_minute: int = 10,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._rate_limiter = _RateLimiter(rate_limit_per_minute)
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_anime(self, title: str, limit: int = 5) -> list[dict]:
        """Returns a list of raw JSON:API anime resource objects."""
        data = await self._get("/anime", params={"filter[text]": title, "page[limit]": limit})
        return data.get("data") or []

    async def get_episodes(self, kitsu_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
        """Returns a list of raw JSON:API episode resource objects."""
        data = await self._get(
            f"/anime/{kitsu_id}/episodes", params={"page[limit]": limit, "page[offset]": offset}
        )
        return data.get("data") or []

    async def _get(self, path: str, params: dict) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            await self._rate_limiter.acquire()

            try:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers={"Accept": "application/vnd.api+json"},
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                backoff = min(2**attempt, 10)
                await asyncio.sleep(backoff)
                continue

            if response.status_code == 429:
                if attempt == self._max_retries:
                    raise KitsuError("Kitsu rate limit exceeded")
                await asyncio.sleep(float(response.headers.get("Retry-After", 5)))
                continue

            if response.status_code >= 500:
                last_error = KitsuError(f"Kitsu returned HTTP {response.status_code}")
                await asyncio.sleep(min(2**attempt, 10))
                continue

            if response.status_code >= 400:
                raise KitsuError(f"Kitsu returned HTTP {response.status_code}")

            try:
                return response.json()
            except ValueError as exc:
                raise KitsuError("Kitsu returned invalid JSON") from exc

        raise KitsuError(f"Kitsu request failed after {self._max_retries} attempts") from last_error
