from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.staff_service import StaffDisplay


def build_staff_list_text(anime_title: str, staff: list[StaffDisplay], page: int) -> str:
    e = html.escape
    header = f"👥 <b>{e(anime_title)} — Staff</b>"
    if page > 1:
        header += f" (page {page})"

    if not staff:
        return header + "\n\nNo staff data available yet."

    lines = [header, ""]
    for s in staff:
        lines.append(f"• {e(s.name)} — {e(s.role)}")

    return "\n".join(lines)


def build_staff_list_keyboard(
    anime_id: int, page: int, has_next_page: bool, origin: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"staff:list:{anime_id}:{page - 1}:{origin}")
        )
    if has_next_page:
        nav_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"staff:list:{anime_id}:{page + 1}:{origin}")
        )
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Back to anime", callback_data=f"anime:v:{anime_id}:{origin}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
