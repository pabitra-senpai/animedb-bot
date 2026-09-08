from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def build_stats_text(stats: dict[str, int]) -> str:
    return (
        "📊 <b>Bot Stats</b>\n\n"
        f"👥 Total users: {stats['total_users']}\n"
        f"🛡️ Admins: {stats['admin_users']}\n"
        f"🚫 Banned: {stats['banned_users']}\n\n"
        f"🎬 Cached anime: {stats['total_anime']}\n"
        f"➕ Watchlist entries: {stats['total_watchlist_entries']}\n"
        f"❤️ Favorites: {stats['total_favorites']}\n"
        f"🕒 History entries: {stats['total_history_entries']}\n"
        f"⭐ Ratings: {stats['total_ratings']}"
    )


def build_broadcast_preview_text(message_text: str, recipient_count: int) -> str:
    e = html.escape
    return (
        "📢 <b>Broadcast Preview</b>\n\n"
        f"Will be sent to <b>{recipient_count}</b> user(s):\n\n"
        f"—————\n{e(message_text)}\n—————\n\n"
        "Confirm sending?"
    )


def build_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm Send", callback_data="bcast:confirm"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="bcast:cancel"),
            ]
        ]
    )


def build_broadcast_result_text(sent: int, failed: int) -> str:
    return f"📢 <b>Broadcast complete</b>\n\n✅ Sent: {sent}\n⚠️ Failed: {failed}"


def build_sync_result_text(synced: int, failed: int) -> str:
    return f"🔄 <b>Manual sync complete</b>\n\n✅ Synced: {synced}\n⚠️ Failed: {failed}"


def build_admin_help_text() -> str:
    return (
        "🛡️ <b>Admin Commands</b>\n\n"
        "/stats — bot-wide usage stats\n"
        "/broadcast &lt;message&gt; — message every user (asks to confirm)\n"
        "/sync — run one background sync pass now\n"
        "/ban &lt;telegram_user_id&gt; — ban a user\n"
        "/unban &lt;telegram_user_id&gt; — unban a user"
    )
