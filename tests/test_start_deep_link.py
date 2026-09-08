from __future__ import annotations

from app.bot.handlers.start import _parse_anime_deep_link


def test_parses_valid_anime_deep_link() -> None:
    assert _parse_anime_deep_link("anime_123") == 123


def test_rejects_non_anime_payload() -> None:
    assert _parse_anime_deep_link("something_else") is None


def test_rejects_non_numeric_id() -> None:
    assert _parse_anime_deep_link("anime_abc") is None


def test_rejects_empty_payload() -> None:
    assert _parse_anime_deep_link("") is None
