from __future__ import annotations

from app.renderers.admin_renderer import (
    build_admin_help_text,
    build_broadcast_confirm_keyboard,
    build_broadcast_preview_text,
    build_broadcast_result_text,
    build_stats_text,
    build_sync_result_text,
)


def test_stats_text_includes_all_fields() -> None:
    stats = {
        "total_users": 10,
        "admin_users": 2,
        "banned_users": 1,
        "total_anime": 50,
        "total_watchlist_entries": 20,
        "total_favorites": 15,
        "total_history_entries": 40,
        "total_ratings": 8,
    }
    text = build_stats_text(stats)
    assert "10" in text
    assert "50" in text
    assert "8" in text


def test_broadcast_preview_escapes_html() -> None:
    text = build_broadcast_preview_text("<script>alert(1)</script>", 5)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "5" in text


def test_broadcast_confirm_keyboard_has_two_buttons() -> None:
    keyboard = build_broadcast_confirm_keyboard()
    buttons = keyboard.inline_keyboard[0]
    assert len(buttons) == 2
    assert buttons[0].callback_data == "bcast:confirm"
    assert buttons[1].callback_data == "bcast:cancel"


def test_broadcast_result_text() -> None:
    text = build_broadcast_result_text(sent=8, failed=2)
    assert "8" in text
    assert "2" in text


def test_sync_result_text() -> None:
    text = build_sync_result_text(synced=5, failed=1)
    assert "5" in text
    assert "1" in text


def test_admin_help_text_lists_commands() -> None:
    text = build_admin_help_text()
    assert "/stats" in text
    assert "/broadcast" in text
    assert "/sync" in text
    assert "/ban" in text
    assert "/unban" in text
