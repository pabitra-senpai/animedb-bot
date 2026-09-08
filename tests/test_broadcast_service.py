from __future__ import annotations

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from app.services.broadcast_service import broadcast_message


class _StubMethod:
    """Minimal stand-in for the aiogram Method object exceptions need."""


class _StubBot:
    def __init__(self, behaviors: dict[int, object]) -> None:
        self.behaviors = behaviors
        self.sent_to: list[int] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        behavior = self.behaviors.get(chat_id)
        if behavior is None:
            self.sent_to.append(chat_id)
            return
        if isinstance(behavior, Exception):
            raise behavior
        self.sent_to.append(chat_id)


@pytest.mark.asyncio
async def test_broadcast_sends_to_all() -> None:
    bot = _StubBot({})
    sent, failed = await broadcast_message(bot, [1, 2, 3], "hello", delay_seconds=0)
    assert sent == 3
    assert failed == 0
    assert bot.sent_to == [1, 2, 3]


@pytest.mark.asyncio
async def test_broadcast_skips_forbidden_without_crashing() -> None:
    bot = _StubBot({2: TelegramForbiddenError(_StubMethod(), "blocked")})
    sent, failed = await broadcast_message(bot, [1, 2, 3], "hello", delay_seconds=0)
    assert sent == 2
    assert failed == 1
    assert 2 not in bot.sent_to


@pytest.mark.asyncio
async def test_broadcast_retries_after_flood_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.broadcast_service.asyncio.sleep", _no_sleep)

    call_count = {2: 0}
    real_send = None

    class _RetryOnceBot(_StubBot):
        async def send_message(self, chat_id: int, text: str) -> None:
            if chat_id == 2:
                call_count[2] += 1
                if call_count[2] == 1:
                    raise TelegramRetryAfter(_StubMethod(), "flood", retry_after=0)
            self.sent_to.append(chat_id)

    bot = _RetryOnceBot({})
    sent, failed = await broadcast_message(bot, [1, 2, 3], "hello", delay_seconds=0)
    assert sent == 3
    assert failed == 0
    assert call_count[2] == 2  # first attempt hit flood wait, second succeeded


async def _no_sleep(_seconds: float) -> None:
    return None
