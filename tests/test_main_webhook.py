from __future__ import annotations

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import Settings
from app.main import _build_web_app, _webhook_path


def test_webhook_path_extracted_from_url() -> None:
    assert _webhook_path("https://example.onrender.com/webhook/abc123") == "/webhook/abc123"


def test_webhook_path_defaults_when_root() -> None:
    assert _webhook_path("https://example.onrender.com") == "/webhook"


def _settings(**overrides) -> Settings:
    base = dict(
        BOT_TOKEN="123456:fake",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.mark.asyncio
async def test_build_web_app_polling_mode_has_only_health_route() -> None:
    settings = _settings()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    app = await _build_web_app(bot, dp, settings)

    paths = {route.resource.canonical for route in app.router.routes()}
    assert "/health" in paths
    assert not any("webhook" in p for p in paths)

    await bot.session.close()


@pytest.mark.asyncio
async def test_build_web_app_webhook_mode_adds_webhook_route() -> None:
    settings = _settings(
        WEBHOOK_URL="https://example.onrender.com/webhook/xyz", WEBHOOK_SECRET="s3cr3t"
    )
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    app = await _build_web_app(bot, dp, settings)

    paths = {route.resource.canonical for route in app.router.routes()}
    assert "/health" in paths
    assert "/webhook/xyz" in paths

    await bot.session.close()
