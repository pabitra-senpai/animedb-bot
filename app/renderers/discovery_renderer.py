from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Anime

DISCOVERY_PER_PAGE = 8


def build_discovery_text(title: str, results: list[Anime], page: int) -> str:
    e = html.escape
    header = f"<b>{e(title)}</b>"
    if page > 1:
        header += f" (page {page})"

    if not results:
        return f"{header}\n\nNothing found."

    return header


def build_discovery_keyboard(
    results: list[Anime], page: int, has_next_page: bool, page_callback_prefix: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for anime in results:
        label = anime.title
        if anime.score is not None:
            label = f"{label} — ⭐{anime.score}"
        if len(label) > 60:
            label = label[:59].rstrip() + "…"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"anime:v:{anime.id}:-")])

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"{page_callback_prefix}{page - 1}")
        )
    if has_next_page:
        nav_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"{page_callback_prefix}{page + 1}")
        )
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_genre_menu_keyboard(genres: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for genre in genres:
        row.append(InlineKeyboardButton(text=genre, callback_data=f"dgen:{genre}:1"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
