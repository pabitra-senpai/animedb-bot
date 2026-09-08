"""
Broadcast: sends one message to every non-banned user, respecting
Telegram's flood limits (small delay between sends, honors
TelegramRetryAfter, skips users who've blocked the bot without treating
that as a hard failure worth alarming an admin over).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

logger = logging.getLogger(__name__)


async def broadcast_message(
    bot: Bot, telegram_user_ids: list[int], text: str, delay_seconds: float = 0.05
) -> tuple[int, int]:
    """Returns (sent_count, failed_count)."""
    sent = 0
    failed = 0

    for telegram_user_id in telegram_user_ids:
        try:
            await bot.send_message(telegram_user_id, text)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(telegram_user_id, text)
                sent += 1
            except Exception:
                logger.warning("broadcast_send_failed_after_retry", extra={"telegram_user_id": telegram_user_id})
                failed += 1
        except TelegramForbiddenError:
            # User blocked the bot or deleted their account — expected
            # over time, not worth logging as a warning.
            failed += 1
        except Exception:
            logger.warning("broadcast_send_failed", extra={"telegram_user_id": telegram_user_id})
            failed += 1

        await asyncio.sleep(delay_seconds)

    logger.info("broadcast_complete", extra={"sent": sent, "failed": failed})
    return sent, failed
