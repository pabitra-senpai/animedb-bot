from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import User


def build_profile_text(user: User, stats: dict[str, int]) -> str:
    e = html.escape
    name = e(user.first_name)
    joined = user.created_at.strftime("%B %Y") if user.created_at else "recently"

    lines = [
        f"👤 <b>{name}'s Profile</b>",
        f"Member since {joined}",
        "",
        f"➕ Watchlist: {stats['watchlist_count']}",
        f"❤️ Favorites: {stats['favorites_count']}",
        f"🕒 Viewed: {stats['history_count']}",
        f"⭐ Rated: {stats['ratings_count']}",
    ]
    return "\n".join(lines)


def build_settings_text(user: User) -> str:
    status = "on ✅" if user.notifications_enabled else "off ❌"
    return f"⚙️ <b>Settings</b>\n\nNotifications: {status}"


def build_settings_keyboard(user: User) -> InlineKeyboardMarkup:
    label = "🔕 Turn off notifications" if user.notifications_enabled else "🔔 Turn on notifications"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="settings:toggle_notifications")]]
    )
