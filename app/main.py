"""
Application entrypoint.

Supports two modes, chosen by whether WEBHOOK_URL is set (see
Settings.use_webhook):

- Long polling (default): simplest, most robust for a single instance.
  No public URL or TLS cert management needed — the natural fit for a
  Render Background Worker. This is what runs if WEBHOOK_URL is unset.
- Webhook: Telegram POSTs updates to WEBHOOK_URL directly. Needs a
  public HTTPS URL (Render's Web Service gives you one automatically)
  and WEBHOOK_SECRET set to a random string, which Telegram echoes back
  in the X-Telegram-Bot-Api-Secret-Token header on every request —
  aiogram's SimpleRequestHandler verifies it automatically and rejects
  anything else. Lower latency than polling, but more moving parts.

Either way, a single aiohttp app serves GET /health (used by Render's
health checks and Docker's HEALTHCHECK) on $PORT, plus the webhook path
when webhook mode is active.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.bot.dispatcher import build_dispatcher
from app.config import Settings, get_settings
from app.db.session import dispose_engine
from app.services.anilist_client import AniListClient
from app.services.jikan_client import JikanClient
from app.services.kitsu_client import KitsuClient
from app.services.sync_job import run_periodic_sync
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def _webhook_path(webhook_url: str) -> str:
    return urlparse(webhook_url).path or "/webhook"


async def _build_web_app(bot: Bot, dp: Dispatcher, settings: Settings) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    # Does not implement keep-alive pings — reports process health only,
    # never generates outbound "ping myself" traffic.
    app.router.add_get("/health", health)

    if settings.use_webhook:
        path = _webhook_path(settings.webhook_url)
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(
            app, path=path
        )
        setup_application(app, dp, bot=bot)

    return app


async def _run_polling(bot: Bot, dp: Dispatcher) -> None:
    logger.info("bot_starting_polling")
    # Drop any updates that queued up while the bot was offline, and make
    # sure no stale webhook is still registered (polling and webhooks are
    # mutually exclusive on Telegram's side).
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.is_production)

    logger.info(
        "bot_startup",
        extra={
            "environment": settings.environment,
            "admin_count": len(settings.admin_id_set),
            "mode": "webhook" if settings.use_webhook else "polling",
        },
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    anilist_client = AniListClient(
        base_url=settings.anilist_api_url,
        rate_limit_per_minute=settings.anilist_rate_limit_per_minute,
        timeout_seconds=settings.anilist_request_timeout_seconds,
    )
    jikan_client = JikanClient(
        base_url=settings.jikan_base_url,
        rate_limit_per_minute=settings.jikan_rate_limit_per_minute,
        timeout_seconds=settings.jikan_request_timeout_seconds,
    )
    kitsu_client = KitsuClient(
        base_url=settings.kitsu_base_url,
        rate_limit_per_minute=settings.kitsu_rate_limit_per_minute,
        timeout_seconds=settings.kitsu_request_timeout_seconds,
    )
    dp = build_dispatcher(anilist_client, jikan_client, kitsu_client)

    app = await _build_web_app(bot, dp, settings)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    logger.info("web_server_started", extra={"port": settings.port})

    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handle_signal)

    polling_task: asyncio.Task | None = None
    if settings.use_webhook:
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret,
            drop_pending_updates=True,
        )
        logger.info("webhook_registered", extra={"path": _webhook_path(settings.webhook_url)})
    else:
        polling_task = asyncio.create_task(_run_polling(bot, dp))

    sync_task: asyncio.Task | None = None
    if settings.background_sync_enabled:
        sync_task = asyncio.create_task(
            run_periodic_sync(
                anilist_client,
                interval_seconds=settings.background_sync_interval_seconds,
                ttl_seconds=settings.cache_ttl_anime,
                batch_size=settings.background_sync_batch_size,
            )
        )

    try:
        await stop_event.wait()
    finally:
        logger.info("bot_shutting_down")
        if polling_task is not None:
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task
        if settings.use_webhook:
            with suppress(Exception):
                await bot.delete_webhook()
        if sync_task is not None:
            sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await sync_task
        await dp.storage.close()
        await bot.session.close()
        await anilist_client.close()
        await jikan_client.close()
        await kitsu_client.close()
        await dispose_engine()
        await runner.cleanup()
        logger.info("bot_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
