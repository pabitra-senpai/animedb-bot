from __future__ import annotations

from app.db.models import Anime
from app.renderers.discovery_renderer import (
    build_discovery_keyboard,
    build_discovery_text,
    build_genre_menu_keyboard,
)


def test_discovery_text_empty() -> None:
    text = build_discovery_text("🔥 Trending Now", [], page=1)
    assert "Nothing found" in text


def test_discovery_text_page_number() -> None:
    text = build_discovery_text("🔥 Trending Now", [Anime(id=1, title="X")], page=2)
    assert "page 2" in text


def test_discovery_keyboard_buttons_and_pagination() -> None:
    results = [Anime(id=1, title="One Piece", score=8.7), Anime(id=2, title="Naruto", score=8.0)]
    keyboard = build_discovery_keyboard(results, page=2, has_next_page=True, page_callback_prefix="disc:trend:page:")

    anime_buttons = [row[0] for row in keyboard.inline_keyboard if row[0].callback_data.startswith("anime:v:")]
    assert len(anime_buttons) == 2
    assert "⭐8.7" in anime_buttons[0].text

    nav_texts = [b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("disc:")]
    assert "disc:trend:page:1" in nav_texts
    assert "disc:trend:page:3" in nav_texts


def test_genre_menu_keyboard_two_per_row() -> None:
    keyboard = build_genre_menu_keyboard(["Action", "Comedy", "Drama"])
    assert len(keyboard.inline_keyboard[0]) == 2
    assert len(keyboard.inline_keyboard[1]) == 1
    assert keyboard.inline_keyboard[0][0].callback_data == "dgen:Action:1"
