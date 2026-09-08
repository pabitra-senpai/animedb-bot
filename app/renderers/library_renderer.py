from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

LIBRARY_PER_PAGE = 8

_TITLES = {
    "wl": "➕ Your Watchlist",
    "fav": "❤️ Your Favorites",
    "hist": "🕒 Recently Viewed",
}

_EMPTY_MESSAGES = {
    "wl": "Your watchlist is empty. Find something with /search and tap ➕ Watchlist.",
    "fav": "No favorites yet. Find something with /search and tap ❤️ Favorite.",
    "hist": "You haven't viewed any anime yet. Try /search to find something.",
}


def build_library_list_text(kind: str, items: list, page: int) -> str:
    e = html.escape
    header = f"<b>{_TITLES[kind]}</b>"
    if page > 1:
        header += f" (page {page})"

    if not items:
        return f"{header}\n\n{_EMPTY_MESSAGES[kind]}"

    lines = [header, ""]
    for item in items:
        anime = item.anime
        line = f"• {e(anime.title)}"
        if anime.season_year:
            line += f" ({anime.season_year})"
        lines.append(line)

    return "\n".join(lines)


def build_library_list_keyboard(
    kind: str, items: list, page: int, has_next_page: bool
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for item in items:
        anime = item.anime
        label = anime.title if len(anime.title) <= 60 else anime.title[:59].rstrip() + "…"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"anime:v:{anime.id}:-")])

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"{kind}:page:{page - 1}"))
    if has_next_page:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"{kind}:page:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)
