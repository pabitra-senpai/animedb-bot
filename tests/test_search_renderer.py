from __future__ import annotations

from app.db.models import Anime
from app.renderers.search_renderer import (
    build_search_results_keyboard,
    build_search_results_text,
)


def _anime(id_: int, title: str, score: float | None = None, year: int | None = None) -> Anime:
    return Anime(id=id_, title=title, score=score, season_year=year)


def test_results_text_for_empty_results() -> None:
    text = build_search_results_text("asdkjqwe", page=1, result_count=0)
    assert "No anime found" in text
    assert "asdkjqwe" in text


def test_results_text_shows_page_number_when_beyond_page_one() -> None:
    text = build_search_results_text("One Piece", page=2, result_count=5)
    assert "page 2" in text


def test_results_text_omits_page_number_on_page_one() -> None:
    text = build_search_results_text("One Piece", page=1, result_count=5)
    assert "page" not in text.lower()


def test_keyboard_has_one_button_per_result() -> None:
    results = [_anime(1, "One Piece"), _anime(2, "Naruto")]
    keyboard = build_search_results_keyboard(results, page=1, has_next_page=False)

    result_buttons = [row[0] for row in keyboard.inline_keyboard if row[0].callback_data.startswith("anime:v:")]
    assert len(result_buttons) == 2
    assert result_buttons[0].callback_data == "anime:v:1:1"
    assert result_buttons[1].callback_data == "anime:v:2:1"


def test_keyboard_prev_button_hidden_on_first_page() -> None:
    keyboard = build_search_results_keyboard([_anime(1, "X")], page=1, has_next_page=True)
    nav_texts = [b.text for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("srch:")]
    assert "◀️ Prev" not in nav_texts
    assert "Next ▶️" in nav_texts


def test_keyboard_prev_and_next_both_present_on_middle_page() -> None:
    keyboard = build_search_results_keyboard([_anime(1, "X")], page=2, has_next_page=True)
    nav_texts = [b.text for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("srch:")]
    assert "◀️ Prev" in nav_texts
    assert "Next ▶️" in nav_texts


def test_keyboard_next_hidden_on_last_page() -> None:
    keyboard = build_search_results_keyboard([_anime(1, "X")], page=2, has_next_page=False)
    nav_texts = [b.text for row in keyboard.inline_keyboard for b in row if b.callback_data.startswith("srch:")]
    assert "Next ▶️" not in nav_texts
    assert "◀️ Prev" in nav_texts


def test_button_label_includes_score_and_year() -> None:
    results = [_anime(1, "One Piece", score=8.7, year=1999)]
    keyboard = build_search_results_keyboard(results, page=1, has_next_page=False)
    label = keyboard.inline_keyboard[0][0].text
    assert "1999" in label
    assert "8.7" in label


def test_button_label_truncated_for_long_titles() -> None:
    long_title = "A" * 100
    results = [_anime(1, long_title)]
    keyboard = build_search_results_keyboard(results, page=1, has_next_page=False)
    label = keyboard.inline_keyboard[0][0].text
    assert len(label) <= 60
    assert label.endswith("…")
