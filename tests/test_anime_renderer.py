from __future__ import annotations

from app.db.models import Anime
from app.renderers.anime_renderer import (
    PHOTO_CAPTION_LIMIT,
    TEXT_MESSAGE_LIMIT,
    build_anime_detail_text,
    build_anime_keyboard,
)


def _sample_anime(**overrides) -> Anime:
    defaults = dict(
        id=1,
        title="One Piece",
        english_title="One Piece",
        native_title="ワンピース",
        format="TV",
        status="RELEASING",
        season="FALL",
        season_year=1999,
        score=8.7,
        rank=3,
        episodes=1000,
        duration_minutes=24,
        source_material="MANGA",
        synopsis="Gol D. Roger was known as the Pirate King...",
        trailer_url="https://www.youtube.com/watch?v=abc123",
    )
    defaults.update(overrides)
    return Anime(**defaults)


def test_detail_text_includes_key_fields() -> None:
    anime = _sample_anime()
    text = build_anime_detail_text(anime, TEXT_MESSAGE_LIMIT, genre_names=["Action"], studio_names=["Toei Animation"])

    assert "One Piece" in text
    assert "ワンピース" in text
    assert "⭐ 8.7/10" in text
    assert "🏆 #3 rated" in text
    assert "1000 episodes" in text
    assert "Action" in text
    assert "Toei Animation" in text


def test_detail_text_skips_english_title_when_identical_to_title() -> None:
    anime = _sample_anime(title="One Piece", english_title="One Piece", native_title=None)
    text = build_anime_detail_text(anime, TEXT_MESSAGE_LIMIT)
    # Only one "One Piece" occurrence expected outside the bold title line —
    # i.e. it should not be duplicated as a redundant subtitle.
    assert text.count("One Piece") == 1


def test_detail_text_respects_photo_caption_limit_with_long_synopsis() -> None:
    anime = _sample_anime(synopsis="A" * 5000)
    text = build_anime_detail_text(anime, PHOTO_CAPTION_LIMIT)
    assert len(text) <= PHOTO_CAPTION_LIMIT


def test_detail_text_respects_text_message_limit_with_long_synopsis() -> None:
    anime = _sample_anime(synopsis="B" * 10000)
    text = build_anime_detail_text(anime, TEXT_MESSAGE_LIMIT)
    assert len(text) <= TEXT_MESSAGE_LIMIT


def test_detail_text_handles_missing_optional_fields() -> None:
    anime = Anime(id=2, title="Untitled Project", format="TV")
    text = build_anime_detail_text(anime, TEXT_MESSAGE_LIMIT)
    assert "Untitled Project" in text


def test_detail_text_escapes_html_in_synopsis_and_title() -> None:
    anime = _sample_anime(title="<script>alert(1)</script>", synopsis="A & B <tag>")
    text = build_anime_detail_text(anime, TEXT_MESSAGE_LIMIT)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&amp; B" in text


def test_keyboard_includes_trailer_and_back_button() -> None:
    anime = _sample_anime()
    keyboard = build_anime_keyboard(anime, from_page=2)
    flat_buttons = [b for row in keyboard.inline_keyboard for b in row]

    trailer_buttons = [b for b in flat_buttons if b.url]
    back_buttons = [b for b in flat_buttons if b.callback_data == "anime:back:2"]

    assert len(trailer_buttons) == 1
    assert len(back_buttons) == 1


def test_keyboard_always_includes_extras_row() -> None:
    anime = _sample_anime(trailer_url=None)
    keyboard = build_anime_keyboard(anime, from_page=None)
    callback_datas = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert f"ep:list:{anime.id}:1:-" in callback_datas
    assert f"char:list:{anime.id}:1:-" in callback_datas
    assert f"staff:list:{anime.id}:1:-" in callback_datas


def test_keyboard_extras_row_encodes_from_page_as_origin() -> None:
    anime = _sample_anime()
    keyboard = build_anime_keyboard(anime, from_page=3)
    callback_datas = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert f"ep:list:{anime.id}:1:3" in callback_datas


def test_keyboard_library_row_reflects_state() -> None:
    anime = _sample_anime()
    keyboard = build_anime_keyboard(
        anime, from_page=None, in_watchlist=True, is_favorite=True, current_rating=8
    )
    library_row_texts = [b.text for b in keyboard.inline_keyboard[0]]
    assert "✅ In Watchlist" in library_row_texts
    assert "💔 Unfavorite" in library_row_texts
    assert "⭐ Rated 8/10" in library_row_texts


def test_keyboard_library_row_default_state() -> None:
    anime = _sample_anime()
    keyboard = build_anime_keyboard(anime, from_page=None)
    library_row_texts = [b.text for b in keyboard.inline_keyboard[0]]
    assert "➕ Watchlist" in library_row_texts
    assert "❤️ Favorite" in library_row_texts
    assert "⭐ Rate" in library_row_texts
