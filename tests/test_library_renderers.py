from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.db.models import Anime
from app.renderers.library_renderer import build_library_list_keyboard, build_library_list_text
from app.renderers.profile_renderer import build_profile_text, build_settings_keyboard, build_settings_text
from app.renderers.rating_renderer import build_rating_menu_keyboard, build_rating_menu_text


@dataclass
class _FakeLibraryItem:
    anime: Anime


def test_library_list_text_empty() -> None:
    text = build_library_list_text("wl", [], page=1)
    assert "empty" in text.lower()


def test_library_list_text_with_items() -> None:
    items = [_FakeLibraryItem(anime=Anime(id=1, title="One Piece", season_year=1999))]
    text = build_library_list_text("fav", items, page=1)
    assert "One Piece" in text
    assert "1999" in text
    assert "Favorites" in text


def test_library_list_keyboard_has_button_per_item() -> None:
    items = [
        _FakeLibraryItem(anime=Anime(id=1, title="One Piece")),
        _FakeLibraryItem(anime=Anime(id=2, title="Naruto")),
    ]
    keyboard = build_library_list_keyboard("wl", items, page=1, has_next_page=False)
    item_buttons = [row[0] for row in keyboard.inline_keyboard if row[0].callback_data.startswith("anime:v:")]
    assert len(item_buttons) == 2
    assert item_buttons[0].callback_data == "anime:v:1:-"


def test_library_list_keyboard_pagination() -> None:
    items = [_FakeLibraryItem(anime=Anime(id=1, title="X"))]
    keyboard = build_library_list_keyboard("hist", items, page=2, has_next_page=True)
    nav_datas = [b.callback_data for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("hist:page:")]
    assert "hist:page:1" in nav_datas
    assert "hist:page:3" in nav_datas


def test_rating_menu_text_shows_current_rating() -> None:
    text = build_rating_menu_text("One Piece", current_rating=7)
    assert "7/10" in text


def test_rating_menu_keyboard_has_ten_buttons_plus_extras() -> None:
    keyboard = build_rating_menu_keyboard(anime_id=5, origin="-", current_rating=None)
    rate_buttons = [
        b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("rate:set:")
    ]
    assert len(rate_buttons) == 10


def test_rating_menu_keyboard_shows_clear_when_rated() -> None:
    keyboard = build_rating_menu_keyboard(anime_id=5, origin="-", current_rating=6)
    clear_buttons = [
        b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("rate:clear:")
    ]
    assert len(clear_buttons) == 1


def test_rating_menu_keyboard_omits_clear_when_unrated() -> None:
    keyboard = build_rating_menu_keyboard(anime_id=5, origin="-", current_rating=None)
    clear_buttons = [
        b for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("rate:clear:")
    ]
    assert len(clear_buttons) == 0


class _FakeUser:
    def __init__(self, first_name="Pabitra", notifications_enabled=True, created_at=None):
        self.first_name = first_name
        self.notifications_enabled = notifications_enabled
        self.created_at = created_at or datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_profile_text_includes_stats() -> None:
    user = _FakeUser()
    stats = {"watchlist_count": 3, "favorites_count": 1, "history_count": 10, "ratings_count": 2}
    text = build_profile_text(user, stats)
    assert "Pabitra" in text
    assert "3" in text
    assert "January 2026" in text


def test_settings_text_reflects_state() -> None:
    on_text = build_settings_text(_FakeUser(notifications_enabled=True))
    off_text = build_settings_text(_FakeUser(notifications_enabled=False))
    assert "on ✅" in on_text
    assert "off ❌" in off_text


def test_settings_keyboard_label_toggles() -> None:
    on_keyboard = build_settings_keyboard(_FakeUser(notifications_enabled=True))
    off_keyboard = build_settings_keyboard(_FakeUser(notifications_enabled=False))
    assert "Turn off" in on_keyboard.inline_keyboard[0][0].text
    assert "Turn on" in off_keyboard.inline_keyboard[0][0].text
