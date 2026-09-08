"""
Renders a page of search results: a short text header plus one inline
button per anime, followed by Prev/Next pagination controls.
"""

from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Anime

RESULTS_PER_PAGE = 5


def build_search_results_text(query: str, page: int, result_count: int) -> str:
    e = html.escape
    if result_count == 0:
        return f"😕 No anime found for “{e(query)}”. Try a different title."
    header = f"🔍 Results for “{e(query)}”"
    if page > 1:
        header += f" — page {page}"
    return header


def _button_label(anime: Anime) -> str:
    label = anime.title
    if anime.season_year:
        label = f"{label} ({anime.season_year})"
    if anime.score is not None:
        label = f"{label} — ⭐{anime.score}"
    # Telegram button text has generous limits, but keep it tidy on mobile.
    if len(label) > 60:
        label = label[:59].rstrip() + "…"
    return label


def build_search_results_keyboard(
    results: list[Anime], page: int, has_next_page: bool
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for anime in results:
        rows.append(
            [InlineKeyboardButton(text=_button_label(anime), callback_data=f"anime:v:{anime.id}:{page}")]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"srch:p:{page - 1}"))
    if has_next_page:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"srch:p:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)
