"""
Normalizes raw Kitsu JSON:API `episode` resources into the same
NormalizedEpisode shape AniList's streamingEpisodes parsing produces, so
both sources feed the same repository upsert path.
"""

from __future__ import annotations

from app.services.metadata_normalizer import NormalizedEpisode
from app.utils.text import normalize_title


def normalize_kitsu_episode(resource: dict) -> NormalizedEpisode | None:
    attrs = resource.get("attributes") or {}
    number = attrs.get("number")
    if number is None:
        return None

    titles = attrs.get("titles") or {}
    title = attrs.get("canonicalTitle") or titles.get("en_jp") or titles.get("en")

    thumbnail = None
    thumbnail_block = attrs.get("thumbnail")
    if isinstance(thumbnail_block, dict):
        thumbnail = thumbnail_block.get("original") or thumbnail_block.get("large")

    return NormalizedEpisode(episode_number=number, title=title, thumbnail_url=thumbnail)


def find_best_kitsu_match(search_results: list[dict], target_normalized_title: str) -> str | None:
    """Best-effort, conservative match: only accepts an exact normalized-
    title match, or the sole result if there's exactly one candidate.
    Returns the Kitsu anime ID, or None if no confident match exists."""
    if not search_results:
        return None

    if len(search_results) == 1:
        return search_results[0].get("id")

    for resource in search_results:
        attrs = resource.get("attributes") or {}
        titles = attrs.get("titles") or {}
        candidates = [attrs.get("canonicalTitle"), titles.get("en"), titles.get("en_jp"), titles.get("ja_jp")]
        for candidate in candidates:
            if candidate and normalize_title(candidate) == target_normalized_title:
                return resource.get("id")

    return None
