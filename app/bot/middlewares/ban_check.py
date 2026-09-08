"""
Runs after EnsureUserMiddleware (needs `user` already in data). Banned
users get a short notice and nothing else runs — no handler, no library
writes, no history recording.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

BANNED_MESSAGE = "🚫 You've been banned from using this bot."


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")

        if user is not None and user.is_banned:
            if isinstance(event, Message):
                await event.answer(BANNED_MESSAGE)
            elif isinstance(event, CallbackQuery):
                await event.answer(BANNED_MESSAGE, show_alert=True)
            return None

        return await handler(event, data)
