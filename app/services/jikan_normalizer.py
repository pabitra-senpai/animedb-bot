"""
Normalizes a raw Jikan `/anime` resource dict. Kept separate from
JikanClient so it's unit-testable without HTTP, matching the pattern
used for AniList.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NormalizedJikanAnime:
    mal_id: int
    title: str
    english_title: str | None
    synopsis: str | None
    poster_url: str | None
    format: str | None
    status: str | None
    episodes: int | None
    score: float | None  # Jikan scores are already on a 0-10 scale
    genre_names: list[str] = field(default_factory=list)


_STATUS_MAP = {
    "Currently Airing": "RELEASING",
    "Finished Airing": "FINISHED",
    "Not yet aired": "NOT_YET_RELEASED",
}


def normalize_jikan_anime(data: dict) -> NormalizedJikanAnime:
    title = data.get("title")
    if not title:
        raise ValueError(f"Jikan anime {data.get('mal_id')} has no usable title")

    images = data.get("images") or {}
    jpg = images.get("jpg") or {}
    poster_url = jpg.get("large_image_url") or jpg.get("image_url")

    genre_names = [
        g["name"]
        for g in (data.get("genres") or []) + (data.get("explicit_genres") or [])
        if g.get("name")
    ]

    return NormalizedJikanAnime(
        mal_id=data["mal_id"],
        title=title,
        english_title=data.get("title_english"),
        synopsis=data.get("synopsis"),
        poster_url=poster_url,
        format=data.get("type"),
        status=_STATUS_MAP.get(data.get("status"), data.get("status")),
        episodes=data.get("episodes"),
        score=data.get("score"),
        genre_names=genre_names,
    )
