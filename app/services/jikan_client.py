"""
Jikan v4 client (unofficial MyAnimeList API).

Verified against current docs/community sources as of this writing:
- REST, base URL https://api.jikan.moe/v4, no API key required for public
  reads.
- Search: GET /anime?q=<query>&limit=<n>
- Detail: GET /anime/{mal_id}
- Rate limit is informally ~3 req/sec / ~60 req/min; this client defaults
  conservatively and self-throttles the same way the AniList client does.
  Re-verify at https://docs.api.jikan.moe before raising the default.

Used only as a fallback in search_service when AniList returns zero
results for a query — Jikan mirrors MyAnimeList, which sometimes has
entries (or matches alternate titles) that AniList's search misses.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

import httpx

logger = logging.getLogger(__name__)


class JikanError(Exception):
    pass


class JikanRateLimitError(JikanError):
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
                    logger.info("jikan_rate_limit_self_throttle", extra={"wait_seconds": round(wait_for, 2)})
                    await asyncio.sleep(wait_for)
            self._timestamps.append(time.monotonic())


class JikanClient:
    def __init__(
        self,
        base_url: str = "https://api.jikan.moe/v4",
        rate_limit_per_minute: int = 30,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
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

    async def search_anime(self, query: str, limit: int = 10) -> list[dict]:
        """Returns a list of raw Jikan anime resource dicts."""
        data = await self._get("/anime", params={"q": query, "limit": limit})
        return data.get("data") or []

    async def get_anime_by_id(self, mal_id: int) -> dict | None:
        try:
            data = await self._get(f"/anime/{mal_id}")
        except JikanError:
            return None
        return data.get("data")

    async def _get(self, path: str, params: dict | None = None) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            await self._rate_limiter.acquire()

            try:
                response = await self._client.get(f"{self._base_url}{path}", params=params)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                backoff = min(2**attempt, 20)
                logger.warning("jikan_transport_error_retrying", extra={"attempt": attempt, "backoff_seconds": backoff})
                await asyncio.sleep(backoff)
                continue

            if response.status_code == 429:
                if attempt == self._max_retries:
                    raise JikanRateLimitError(f"Jikan rate limit exceeded after {attempt} attempts")
                retry_after = float(response.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after)
                continue

            if response.status_code == 404:
                raise JikanError("Not found")

            if response.status_code >= 500:
                last_error = JikanError(f"Jikan returned HTTP {response.status_code}")
                backoff = min(2**attempt, 20)
                await asyncio.sleep(backoff)
                continue

            if response.status_code >= 400:
                raise JikanError(f"Jikan returned HTTP {response.status_code}")

            try:
                return response.json()
            except ValueError as exc:
                raise JikanError("Jikan returned invalid JSON") from exc

        raise JikanError(f"Jikan request failed after {self._max_retries} attempts") from last_error
