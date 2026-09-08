from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.episode_service import EpisodeDisplay


def build_episode_list_text(anime_title: str, episodes: list[EpisodeDisplay], page: int) -> str:
    e = html.escape
    header = f"📺 <b>{e(anime_title)} — Episodes</b>"
    if page > 1:
        header += f" (page {page})"

    if not episodes:
        return header + "\n\nNo episode data available yet."

    lines = [header, ""]
    for ep in episodes:
        line = f"Ep {ep.number}"
        if ep.title:
            line += f" — {e(ep.title)}"
        if ep.air_date:
            line += f" ({ep.air_date.isoformat()})"
        lines.append(line)

    return "\n".join(lines)


def build_episode_list_keyboard(
    anime_id: int, page: int, has_next_page: bool, origin: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"ep:list:{anime_id}:{page - 1}:{origin}")
        )
    if has_next_page:
        nav_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"ep:list:{anime_id}:{page + 1}:{origin}")
        )
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Back to anime", callback_data=f"anime:v:{anime_id}:{origin}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
