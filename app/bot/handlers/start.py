"""
/start and /help handlers.

/start also supports deep links: /start anime_123 resolves straight to
that anime's detail card (e.g. from a shared link or another bot).
"""

from __future__ import annotations

import html
import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, User

logger = logging.getLogger(__name__)

router = Router(name="start")

WELCOME_TEXT = (
    "🎬 <b>Welcome to AnimeDB Bot</b>\n\n"
    "Search, discover and track anime — right here in Telegram.\n\n"
    "Try:\n"
    "<code>/search One Piece</code>\n\n"
    "Use /help to see everything I can do."
)

HELP_TEXT = (
    "📖 <b>AnimeDB Bot — Help</b>\n\n"
    "<b>Discovery</b>\n"
    "/search &lt;title&gt; — search for an anime\n"
    "/trending — trending anime\n"
    "/popular — most popular anime\n"
    "/top /toprated — top rated anime\n"
    "/airing — currently airing\n"
    "/upcoming — upcoming anime\n"
    "/seasonal — this season's anime\n"
    "/genres — browse by genre\n\n"
    "<b>Your library</b>\n"
    "/watchlist — anime you plan to watch\n"
    "/favorites — your favorite anime\n"
    "/history — recently viewed anime\n"
    "/profile — your stats\n"
    "/settings — notification &amp; preference settings\n\n"
    "/cancel — cancel the current action\n"
    "/help — show this message"
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, user: User) -> None:
    payload = command.args  # e.g. "anime_123" from a deep link
    logger.info(
        "start_command",
        extra={
            "telegram_user_id": message.from_user.id if message.from_user else None,
            "deep_link_payload": payload,
        },
    )

    if payload:
        anime_id = _parse_anime_deep_link(payload)
        if anime_id is not None:
            anime = await session.get(Anime, anime_id)
            if anime is not None:
                # Imported here (not at module top) to avoid a circular
                # import between the start and search handler modules.
                from app.bot.handlers.search import send_anime_detail

                await send_anime_detail(message, anime, session, user, from_page=None)
                return

        safe_payload = html.escape(payload)
        await message.answer(
            f"{WELCOME_TEXT}\n\n"
            f"⚠️ Couldn't open <code>{safe_payload}</code> — it may no longer exist."
        )
        return

    await message.answer(WELCOME_TEXT)


def _parse_anime_deep_link(payload: str) -> int | None:
    if not payload.startswith("anime_"):
        return None
    try:
        return int(payload.removeprefix("anime_"))
    except ValueError:
        return None


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    text = HELP_TEXT
    if user.is_admin:
        from app.renderers.admin_renderer import build_admin_help_text

        text = f"{text}\n\n{build_admin_help_text()}"
    await message.answer(text)
