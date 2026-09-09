"""
Catches any unhandled exception from a handler so:
- the bot process never crashes because of one bad update
- the user gets a polished, non-leaky error message
- the real exception is logged with context for debugging
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

logger = logging.getLogger(__name__)

USER_FACING_ERROR = (
    "⚠️ <b>Something went wrong</b>\n\n"
    "I couldn't complete that action right now. Please try again."
)


class ErrorHandlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            # Registered via dp.update.outer_middleware(), so `event` here
            # is the raw Update, which already carries update_id directly.
            update_id = getattr(event, "update_id", None)
            logger.exception(
                "unhandled_update_exception",
                extra={"update_id": update_id, "event_type": type(event).__name__},
            )

            # Best-effort: tell the user something went wrong without leaking
            # internals. Never let a failure here raise again.
            try:
                inner = event
                if isinstance(inner, Update):
                    inner = inner.message or inner.edited_message or inner.callback_query

                if isinstance(inner, Message):
                    await inner.answer(USER_FACING_ERROR)
                elif isinstance(inner, CallbackQuery):
                    await inner.answer("Something went wrong. Please try again.", show_alert=True)
            except Exception:
                logger.exception("failed_to_send_error_message")

            return None
            
