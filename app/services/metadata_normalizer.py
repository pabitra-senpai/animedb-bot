"""
Converts a raw AniList `Media` dict (as returned by AniListClient) into the
shapes our repositories expect. Kept separate from the client so the
normalization logic is unit-testable without any HTTP involved, and so a
future second primary source doesn't require touching the client.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.utils.text import normalize_title

# AniList scores are 0-100; our schema stores 0-10 to one decimal place,
# matching the "Score: 8.72/10" style shown in the UX spec.
_SCORE_SCALE = 10.0

# AniList's streamingEpisodes titles look like "Episode 12 - Some Title" or
# just "Episode 12". Best-effort parse; anything that doesn't match is
# skipped rather than guessing at an episode number.
_EPISODE_TITLE_RE = re.compile(r"^\s*Episode\s+(\d+)\s*(?:[-:]\s*(.*))?$", re.IGNORECASE)


@dataclass
class NormalizedTitle:
    title: str
    title_type: str  # "romaji" | "english" | "native" | "synonym"
    normalized_title: str


@dataclass
class NormalizedStudio:
    anilist_id: int | None
    name: str


@dataclass
class NormalizedEpisode:
    episode_number: int
    title: str | None
    thumbnail_url: str | None


@dataclass
class NormalizedVoiceActor:
    anilist_id: int
    name_full: str
    name_native: str | None
    image_url: str | None
    language: str


@dataclass
class NormalizedCharacterEdge:
    character_anilist_id: int
    name_full: str
    name_native: str | None
    image_url: str | None
    role: str
    voice_actors: list[NormalizedVoiceActor] = field(default_factory=list)


@dataclass
class NormalizedStaffEdge:
    staff_anilist_id: int
    name_full: str
    name_native: str | None
    image_url: str | None
    role: str


@dataclass
class NormalizedAnime:
    anilist_id: int
    mal_id: int | None
    title: str
    english_title: str | None
    native_title: str | None
    romaji_title: str | None
    synopsis: str | None
    poster_url: str | None
    banner_url: str | None
    trailer_url: str | None
    format: str | None
    status: str | None
    season: str | None
    season_year: int | None
    episodes: int | None
    duration_minutes: int | None
    source_material: str | None
    score: float | None
    popularity: int | None
    rank: int | None
    favourites_count: int | None
    country_of_origin: str | None
    titles: list[NormalizedTitle] = field(default_factory=list)
    genre_names: list[str] = field(default_factory=list)
    studios: list[NormalizedStudio] = field(default_factory=list)
    episode_entries: list[NormalizedEpisode] = field(default_factory=list)


def _build_trailer_url(trailer: dict | None) -> str | None:
    if not trailer:
        return None
    trailer_id = trailer.get("id")
    site = (trailer.get("site") or "").lower()
    if not trailer_id:
        return None
    if site == "youtube":
        return f"https://www.youtube.com/watch?v={trailer_id}"
    if site == "dailymotion":
        return f"https://www.dailymotion.com/video/{trailer_id}"
    return None


def _first_ranking_of_type(rankings: list[dict] | None, rank_type: str) -> int | None:
    for entry in rankings or []:
        if entry.get("type") == rank_type and entry.get("context") == "all time":
            return entry.get("rank")
    # Fall back to any ranking of the requested type if no "all time" entry exists.
    for entry in rankings or []:
        if entry.get("type") == rank_type:
            return entry.get("rank")
    return None


def normalize_anilist_media(media: dict) -> NormalizedAnime:
    """`media` is one element of the `media` array from a Page/Media query."""

    title_block = media.get("title") or {}
    romaji = title_block.get("romaji")
    english = title_block.get("english")
    native = title_block.get("native")

    display_title = romaji or english or native
    if not display_title:
        raise ValueError(f"AniList media {media.get('id')} has no usable title")

    titles: list[NormalizedTitle] = []
    seen_normalized: set[str] = set()

    def _add_title(value: str | None, title_type: str) -> None:
        if not value:
            return
        norm = normalize_title(value)
        if norm in seen_normalized:
            return
        seen_normalized.add(norm)
        titles.append(NormalizedTitle(title=value, title_type=title_type, normalized_title=norm))

    _add_title(romaji, "romaji")
    _add_title(english, "english")
    _add_title(native, "native")
    for synonym in media.get("synonyms") or []:
        _add_title(synonym, "synonym")

    cover_image = media.get("coverImage") or {}
    poster_url = cover_image.get("extraLarge") or cover_image.get("large")

    average_score = media.get("averageScore")
    score = round(average_score / _SCORE_SCALE, 2) if average_score is not None else None

    studios_block = (media.get("studios") or {}).get("nodes") or []
    studios = [
        NormalizedStudio(anilist_id=s.get("id"), name=s["name"])
        for s in studios_block
        if s.get("name")
    ]

    episode_entries: list[NormalizedEpisode] = []
    seen_episode_numbers: set[int] = set()
    for entry in media.get("streamingEpisodes") or []:
        raw_title = entry.get("title")
        if not raw_title:
            continue
        match = _EPISODE_TITLE_RE.match(raw_title)
        if not match:
            continue
        number = int(match.group(1))
        if number in seen_episode_numbers:
            continue
        seen_episode_numbers.add(number)
        parsed_title = (match.group(2) or "").strip() or None
        episode_entries.append(
            NormalizedEpisode(
                episode_number=number,
                title=parsed_title,
                thumbnail_url=entry.get("thumbnail"),
            )
        )
    episode_entries.sort(key=lambda e: e.episode_number)

    return NormalizedAnime(
        anilist_id=media["id"],
        mal_id=media.get("idMal"),
        title=display_title,
        english_title=english,
        native_title=native,
        romaji_title=romaji,
        synopsis=media.get("description"),
        poster_url=poster_url,
        banner_url=media.get("bannerImage"),
        trailer_url=_build_trailer_url(media.get("trailer")),
        format=media.get("format"),
        status=media.get("status"),
        season=media.get("season"),
        season_year=media.get("seasonYear"),
        episodes=media.get("episodes"),
        duration_minutes=media.get("duration"),
        source_material=media.get("source"),
        score=score,
        popularity=media.get("popularity"),
        rank=_first_ranking_of_type(media.get("rankings"), "RATED"),
        favourites_count=media.get("favourites"),
        country_of_origin=media.get("countryOfOrigin"),
        titles=titles,
        genre_names=media.get("genres") or [],
        studios=studios,
        episode_entries=episode_entries,
    )


def normalize_characters_page(characters_connection: dict) -> tuple[list[NormalizedCharacterEdge], bool]:
    """`characters_connection` is the raw `characters` field from the
    characters query: {pageInfo: {hasNextPage}, edges: [...]}."""
    edges = characters_connection.get("edges") or []
    has_next_page = bool((characters_connection.get("pageInfo") or {}).get("hasNextPage"))

    results: list[NormalizedCharacterEdge] = []
    for edge in edges:
        node = edge.get("node") or {}
        name_block = node.get("name") or {}
        name_full = name_block.get("full")
        if not node.get("id") or not name_full:
            continue

        voice_actors = []
        for va in edge.get("voiceActors") or []:
            va_name = (va.get("name") or {}).get("full")
            if not va.get("id") or not va_name:
                continue
            voice_actors.append(
                NormalizedVoiceActor(
                    anilist_id=va["id"],
                    name_full=va_name,
                    name_native=(va.get("name") or {}).get("native"),
                    image_url=(va.get("image") or {}).get("large"),
                    language="JAPANESE",
                )
            )

        results.append(
            NormalizedCharacterEdge(
                character_anilist_id=node["id"],
                name_full=name_full,
                name_native=name_block.get("native"),
                image_url=(node.get("image") or {}).get("large"),
                role=edge.get("role") or "BACKGROUND",
                voice_actors=voice_actors,
            )
        )

    return results, has_next_page


def normalize_staff_page(staff_connection: dict) -> tuple[list[NormalizedStaffEdge], bool]:
    """`staff_connection` is the raw `staff` field from the staff query:
    {pageInfo: {hasNextPage}, edges: [...]}."""
    edges = staff_connection.get("edges") or []
    has_next_page = bool((staff_connection.get("pageInfo") or {}).get("hasNextPage"))

    results: list[NormalizedStaffEdge] = []
    for edge in edges:
        node = edge.get("node") or {}
        name_block = node.get("name") or {}
        name_full = name_block.get("full")
        if not node.get("id") or not name_full:
            continue

        results.append(
            NormalizedStaffEdge(
                staff_anilist_id=node["id"],
                name_full=name_full,
                name_native=name_block.get("native"),
                image_url=(node.get("image") or {}).get("large"),
                role=edge.get("role") or "Staff",
            )
        )

    return results, has_next_page
