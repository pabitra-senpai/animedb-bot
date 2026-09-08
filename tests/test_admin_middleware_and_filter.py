from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from app.bot.filters.admin_filter import IsAdmin
from app.bot.middlewares.ban_check import BANNED_MESSAGE, BanCheckMiddleware
from app.db.models import User


def _mock_message() -> MagicMock:
    message = MagicMock(spec=Message)
    message.answer = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_ban_check_blocks_banned_user() -> None:
    middleware = BanCheckMiddleware()
    message = _mock_message()
    handler_called = {"value": False}

    async def handler(event, data):
        handler_called["value"] = True

    banned_user = User(telegram_user_id=1, first_name="X", is_banned=True)
    await middleware(handler, message, {"user": banned_user})

    assert handler_called["value"] is False
    message.answer.assert_awaited_once_with(BANNED_MESSAGE)


@pytest.mark.asyncio
async def test_ban_check_allows_non_banned_user() -> None:
    middleware = BanCheckMiddleware()
    message = _mock_message()
    handler_called = {"value": False}

    async def handler(event, data):
        handler_called["value"] = True
        return "handler_result"

    active_user = User(telegram_user_id=1, first_name="X", is_banned=False)
    result = await middleware(handler, message, {"user": active_user})

    assert handler_called["value"] is True
    assert result == "handler_result"
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_ban_check_passes_through_when_no_user_in_data() -> None:
    middleware = BanCheckMiddleware()
    message = _mock_message()
    handler_called = {"value": False}

    async def handler(event, data):
        handler_called["value"] = True

    await middleware(handler, message, {})
    assert handler_called["value"] is True


@pytest.mark.asyncio
async def test_is_admin_filter_true_for_admin() -> None:
    is_admin_filter = IsAdmin()
    admin_user = User(telegram_user_id=1, first_name="X", is_admin=True)
    result = await is_admin_filter(SimpleNamespace(), user=admin_user)
    assert result is True


@pytest.mark.asyncio
async def test_is_admin_filter_false_for_regular_user() -> None:
    is_admin_filter = IsAdmin()
    regular_user = User(telegram_user_id=1, first_name="X", is_admin=False)
    result = await is_admin_filter(SimpleNamespace(), user=regular_user)
    assert result is False
