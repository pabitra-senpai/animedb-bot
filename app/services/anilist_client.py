"""
AniList GraphQL client.

Verified against current official docs (docs.anilist.co) as of this
writing:
- Single POST endpoint, JSON body of {query, variables}. No API key
  required for public media queries.
- Nominal rate limit: 90 req/min via X-RateLimit-Limit /
  X-RateLimit-Remaining response headers. The API is CURRENTLY in a
  degraded state capped at 30 req/min — see Settings.anilist_rate_limit_per_minute,
  which defaults conservatively. Re-check docs.anilist.co/guide/rate-limiting
  before raising it.
- 429 responses include Retry-After (seconds) and X-RateLimit-Reset
  (unix timestamp) headers, plus a GraphQL-shaped error body.
- There is also a separate, undocumented-threshold burst limiter — bursts
  of requests should be avoided even when under the per-minute cap.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

import httpx

logger = logging.getLogger(__name__)


class AniListError(Exception):
    """Raised for AniList errors that are not worth retrying (bad query, 404, etc.)."""


class AniListRateLimitError(AniListError):
    """Raised if a 429 persists after all configured retries."""


class AniListUnavailableError(AniListError):
    """Raised when AniList reports a full API outage (403 + outage message)."""


# --- GraphQL documents ---
# Keep queries focused on what the search/detail views actually render;
# fields can be extended as later phases (episodes/characters/staff) need more.

SEARCH_ANIME_QUERY = """
query ($search: String, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
    }
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      ...AnimeFields
    }
  }
}
""" + "{anime_fields}"

GET_ANIME_BY_ID_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    ...AnimeFields
  }
}
""" + "{anime_fields}"

_ANIME_FIELDS_FRAGMENT = """
fragment AnimeFields on Media {
  id
  idMal
  title {
    romaji
    english
    native
  }
  synonyms
  description(asHtml: false)
  coverImage {
    extraLarge
    large
    color
  }
  bannerImage
  trailer {
    id
    site
  }
  averageScore
  meanScore
  popularity
  favourites
  rankings {
    rank
    type
    context
  }
  genres
  studios(isMain: true) {
    nodes {
      id
      name
    }
  }
  format
  status
  season
  seasonYear
  episodes
  duration
  source
  countryOfOrigin
  streamingEpisodes {
    title
    thumbnail
  }
}
"""

SEARCH_ANIME_QUERY = SEARCH_ANIME_QUERY.replace("{anime_fields}", _ANIME_FIELDS_FRAGMENT)
GET_ANIME_BY_ID_QUERY = GET_ANIME_BY_ID_QUERY.replace("{anime_fields}", _ANIME_FIELDS_FRAGMENT)

GET_ANIME_CHARACTERS_QUERY = """
query ($id: Int, $page: Int, $perPage: Int) {
  Media(id: $id, type: ANIME) {
    characters(page: $page, perPage: $perPage, sort: [ROLE, RELEVANCE]) {
      pageInfo {
        hasNextPage
      }
      edges {
        role
        voiceActors(language: JAPANESE) {
          id
          name {
            full
            native
          }
          image {
            large
          }
        }
        node {
          id
          name {
            full
            native
          }
          image {
            large
          }
        }
      }
    }
  }
}
"""

GET_ANIME_STAFF_QUERY = """
query ($id: Int, $page: Int, $perPage: Int) {
  Media(id: $id, type: ANIME) {
    staff(page: $page, perPage: $perPage, sort: RELEVANCE) {
      pageInfo {
        hasNextPage
      }
      edges {
        role
        node {
          id
          name {
            full
            native
          }
          image {
            large
          }
        }
      }
    }
  }
}
"""

# Used by discovery browsing (trending/popular/top-rated/airing/upcoming/
# seasonal/genre). All filter variables are optional and nullable — the
# caller only includes the ones it needs in the variables dict; per
# AniList's own docs, a declared-but-unsupplied variable is simply
# ignored, so this one query string covers every browse mode.
BROWSE_ANIME_QUERY = """
query ($sort: [MediaSort], $page: Int, $perPage: Int, $status: MediaStatus, $season: MediaSeason, $seasonYear: Int, $genre_in: [String]) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      hasNextPage
    }
    media(type: ANIME, sort: $sort, status: $status, season: $season, seasonYear: $seasonYear, genre_in: $genre_in) {
      ...AnimeFields
    }
  }
}
""" + "{anime_fields}"

BROWSE_ANIME_QUERY = BROWSE_ANIME_QUERY.replace("{anime_fields}", _ANIME_FIELDS_FRAGMENT)


class _RateLimiter:
    """Sliding-window limiter: blocks callers once `max_per_minute` requests
    have gone out in the trailing 60s, rather than reacting only after a 429."""

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
                    logger.info("anilist_rate_limit_self_throttle", extra={"wait_seconds": round(wait_for, 2)})
                    await asyncio.sleep(wait_for)

            self._timestamps.append(time.monotonic())


class AniListClient:
    def __init__(
        self,
        base_url: str,
        rate_limit_per_minute: int = 25,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._max_retries = max_retries
        self._rate_limiter = _RateLimiter(rate_limit_per_minute)
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AniListClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def search_anime(self, query: str, page: int = 1, per_page: int = 10) -> dict:
        """Returns the raw `Page` object: {pageInfo: {...}, media: [...]}."""
        data = await self._request(
            SEARCH_ANIME_QUERY, {"search": query, "page": page, "perPage": per_page}
        )
        return data["Page"]

    async def get_anime_by_id(self, anilist_id: int) -> dict | None:
        data = await self._request(GET_ANIME_BY_ID_QUERY, {"id": anilist_id})
        return data.get("Media")

    async def get_anime_characters(self, anilist_id: int, page: int = 1, per_page: int = 10) -> dict:
        """Returns the raw `characters` connection: {pageInfo: {...}, edges: [...]}."""
        data = await self._request(
            GET_ANIME_CHARACTERS_QUERY, {"id": anilist_id, "page": page, "perPage": per_page}
        )
        media = data.get("Media")
        if media is None:
            return {"pageInfo": {"hasNextPage": False}, "edges": []}
        return media["characters"]

    async def get_anime_staff(self, anilist_id: int, page: int = 1, per_page: int = 10) -> dict:
        """Returns the raw `staff` connection: {pageInfo: {...}, edges: [...]}."""
        data = await self._request(
            GET_ANIME_STAFF_QUERY, {"id": anilist_id, "page": page, "perPage": per_page}
        )
        media = data.get("Media")
        if media is None:
            return {"pageInfo": {"hasNextPage": False}, "edges": []}
        return media["staff"]

    async def browse_anime(
        self,
        sort: list[str],
        page: int = 1,
        per_page: int = 10,
        status: str | None = None,
        season: str | None = None,
        season_year: int | None = None,
        genres: list[str] | None = None,
    ) -> dict:
        """Returns the raw `Page` object for a discovery/browse listing —
        no search string, just sort + optional filters."""
        variables: dict = {"sort": sort, "page": page, "perPage": per_page}
        if status is not None:
            variables["status"] = status
        if season is not None:
            variables["season"] = season
        if season_year is not None:
            variables["seasonYear"] = season_year
        if genres:
            variables["genre_in"] = genres

        data = await self._request(BROWSE_ANIME_QUERY, variables)
        return data["Page"]

    async def _request(self, query: str, variables: dict) -> dict:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            await self._rate_limiter.acquire()

            try:
                response = await self._client.post(
                    self._base_url,
                    json={"query": query, "variables": variables},
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc
                backoff = min(2 ** attempt, 20)
                logger.warning(
                    "anilist_transport_error_retrying",
                    extra={"attempt": attempt, "backoff_seconds": backoff, "error": str(exc)},
                )
                await asyncio.sleep(backoff)
                continue

            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining is not None:
                logger.debug("anilist_rate_limit_remaining", extra={"remaining": remaining})

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 60))
                logger.warning(
                    "anilist_rate_limited",
                    extra={"attempt": attempt, "retry_after_seconds": retry_after},
                )
                if attempt == self._max_retries:
                    raise AniListRateLimitError(
                        f"AniList rate limit exceeded after {attempt} attempts"
                    )
                await asyncio.sleep(retry_after)
                continue

            if response.status_code == 403:
                body = _safe_json(response)
                message = _first_error_message(body) or "AniList API unavailable"
                raise AniListUnavailableError(message)

            if response.status_code >= 500:
                last_error = AniListError(f"AniList returned HTTP {response.status_code}")
                backoff = min(2 ** attempt, 20)
                logger.warning(
                    "anilist_server_error_retrying",
                    extra={"attempt": attempt, "status": response.status_code, "backoff_seconds": backoff},
                )
                await asyncio.sleep(backoff)
                continue

            body = _safe_json(response)

            if response.status_code >= 400:
                message = _first_error_message(body) or f"AniList returned HTTP {response.status_code}"
                raise AniListError(message)

            if body.get("errors"):
                raise AniListError(_first_error_message(body) or "Unknown AniList GraphQL error")

            return body["data"]

        raise AniListError(f"AniList request failed after {self._max_retries} attempts") from last_error


def _safe_json(response: httpx.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {}


def _first_error_message(body: dict) -> str | None:
    errors = body.get("errors") or []
    if errors and isinstance(errors, list):
        return errors[0].get("message")
    return None
