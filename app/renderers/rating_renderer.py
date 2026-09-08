from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_rating_menu_text(anime_title: str, current_rating: int | None) -> str:
    e = html.escape
    text = f"⭐ <b>Rate {e(anime_title)}</b>\n\nPick a score from 1 to 10:"
    if current_rating:
        text += f"\n\nYour current rating: {current_rating}/10"
    return text


def build_rating_menu_keyboard(anime_id: int, origin: str, current_rating: int | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    number_buttons = [
        InlineKeyboardButton(
            text=f"⭐{n}" if n != current_rating else f"✅{n}",
            callback_data=f"rate:set:{anime_id}:{n}:{origin}",
        )
        for n in range(1, 11)
    ]
    # 5 per row -> two rows of buttons for a 1-10 grid.
    rows.append(number_buttons[:5])
    rows.append(number_buttons[5:])

    if current_rating is not None:
        rows.append(
            [InlineKeyboardButton(text="🗑️ Clear rating", callback_data=f"rate:clear:{anime_id}:{origin}")]
        )

    rows.append([InlineKeyboardButton(text="🔙 Back to anime", callback_data=f"anime:v:{anime_id}:{origin}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
