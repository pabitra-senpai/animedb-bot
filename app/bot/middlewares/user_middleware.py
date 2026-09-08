"""
Runs after DbSessionMiddleware (needs `session` already in data). Looks up
or creates the User row for whoever sent this update and makes it
available to handlers as the `user` parameter.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TelegramUser

from app.config import get_settings
from app.db.repositories.user_repository import get_or_create_user


class EnsureUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = _extract_from_user(event)

        if telegram_user is not None:
            session = data["session"]
            data["user"] = await get_or_create_user(
                session,
                telegram_user_id=telegram_user.id,
                first_name=telegram_user.first_name,
                username=telegram_user.username,
                last_name=telegram_user.last_name,
                language_code=telegram_user.language_code,
                admin_ids=get_settings().admin_id_set,
            )

        return await handler(event, data)


def _extract_from_user(event: TelegramObject) -> TelegramUser | None:
    if isinstance(event, Message):
        return event.from_user
    if isinstance(event, CallbackQuery):
        return event.from_user
    return None
