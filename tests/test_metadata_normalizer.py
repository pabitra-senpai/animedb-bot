from __future__ import annotations

import pytest

from app.services.metadata_normalizer import normalize_anilist_media, normalize_characters_page, normalize_staff_page
from tests.fixtures.anilist_samples import (
    CHARACTERS_CONNECTION,
    MEDIA_WITH_STREAMING_EPISODES,
    MINIMAL_MEDIA,
    NO_TITLE_MEDIA,
    ONE_PIECE_MEDIA,
    STAFF_CONNECTION,
)


def test_normalizes_full_media_record() -> None:
    normalized = normalize_anilist_media(ONE_PIECE_MEDIA)

    assert normalized.anilist_id == 21
    assert normalized.mal_id == 21
    assert normalized.title == "One Piece"
    assert normalized.score == 8.7
    assert normalized.rank == 3  # RATED / all time
    assert normalized.trailer_url == "https://www.youtube.com/watch?v=S5-vZfW1Cc4"
    assert normalized.genre_names == ["Action", "Adventure", "Fantasy"]
    assert [s.name for s in normalized.studios] == ["Toei Animation"]

    # Romaji and English happen to both be "One Piece" here — dedup by
    # normalized value means English is skipped, not stored twice.
    title_types = {t.title_type for t in normalized.titles}
    assert title_types == {"romaji", "native", "synonym"}
    normalized_values = [t.normalized_title for t in normalized.titles]
    assert normalized_values.count("one piece") == 1


def test_falls_back_to_english_title_when_romaji_missing() -> None:
    normalized = normalize_anilist_media(MINIMAL_MEDIA)

    assert normalized.title == "Untitled Project"
    assert normalized.score is None
    assert normalized.rank is None
    assert normalized.studios == []
    assert normalized.poster_url is None
    assert normalized.trailer_url is None


def test_raises_on_completely_missing_title() -> None:
    with pytest.raises(ValueError):
        normalize_anilist_media(NO_TITLE_MEDIA)


def test_score_scaled_from_100_to_10() -> None:
    media = dict(MINIMAL_MEDIA, averageScore=93)
    normalized = normalize_anilist_media(media)
    assert normalized.score == 9.3


def test_parses_streaming_episodes_into_episode_entries() -> None:
    normalized = normalize_anilist_media(MEDIA_WITH_STREAMING_EPISODES)

    numbers = [e.episode_number for e in normalized.episode_entries]
    assert numbers == [1, 2, 5]  # sorted, deduped (second "Episode 1" dropped)

    ep1 = normalized.episode_entries[0]
    assert ep1.title == "Romance Dawn, the Great Swordsman!"
    assert ep1.thumbnail_url == "https://example.com/1.jpg"

    ep5 = normalized.episode_entries[2]
    assert ep5.title is None  # "Episode 5" has no " - title" suffix
    assert ep5.thumbnail_url is None


def test_ignores_streaming_episode_titles_that_dont_match_pattern() -> None:
    media = dict(MINIMAL_MEDIA, streamingEpisodes=[{"title": "Not an episode title", "thumbnail": None}])
    normalized = normalize_anilist_media(media)
    assert normalized.episode_entries == []


def test_missing_streaming_episodes_key_handled_gracefully() -> None:
    normalized = normalize_anilist_media(MINIMAL_MEDIA)
    assert normalized.episode_entries == []


def test_normalize_characters_page() -> None:
    edges, has_next = normalize_characters_page(CHARACTERS_CONNECTION)

    assert has_next is True
    assert len(edges) == 2

    luffy = edges[0]
    assert luffy.character_anilist_id == 40
    assert luffy.name_full == "Monkey D. Luffy"
    assert luffy.role == "MAIN"
    assert len(luffy.voice_actors) == 1
    assert luffy.voice_actors[0].name_full == "Mayumi Tanaka"
    assert luffy.voice_actors[0].language == "JAPANESE"

    nami = edges[1]
    assert nami.role == "SUPPORTING"
    assert nami.voice_actors == []


def test_normalize_characters_page_skips_malformed_edges() -> None:
    connection = {
        "pageInfo": {"hasNextPage": False},
        "edges": [{"role": "MAIN", "voiceActors": [], "node": {"id": None, "name": {"full": None}}}],
    }
    edges, has_next = normalize_characters_page(connection)
    assert edges == []
    assert has_next is False


def test_normalize_staff_page() -> None:
    edges, has_next = normalize_staff_page(STAFF_CONNECTION)

    assert has_next is False
    assert len(edges) == 2
    assert edges[0].staff_anilist_id == 500
    assert edges[0].role == "Director"
    assert edges[1].name_full == "Eiichiro Oda"


def test_normalize_staff_page_skips_malformed_edges() -> None:
    connection = {"pageInfo": {}, "edges": [{"role": "X", "node": {"id": 1, "name": {}}}]}
    edges, has_next = normalize_staff_page(connection)
    assert edges == []
    assert has_next is False
