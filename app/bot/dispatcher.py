"""
Builds the aiogram Dispatcher: registers routers, middlewares, and
workflow data (long-lived objects like the AniList client that handlers
receive as ordinary parameters).

This file stays the single place that wires everything together as more
routers are added in later phases.
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import admin, anime_extras, discovery, library, profile, search, start
from app.bot.middlewares.ban_check import BanCheckMiddleware
from app.bot.middlewares.db_session import DbSessionMiddleware
from app.bot.middlewares.error_handling import ErrorHandlingMiddleware
from app.bot.middlewares.user_middleware import EnsureUserMiddleware
from app.services.anilist_client import AniListClient
from app.services.jikan_client import JikanClient
from app.services.kitsu_client import KitsuClient

logger = logging.getLogger(__name__)


def build_dispatcher(
    anilist_client: AniListClient, jikan_client: JikanClient, kitsu_client: KitsuClient
) -> Dispatcher:
    # MemoryStorage is fine while there's a single bot instance. Multi-step
    # flows that need to survive restarts/scaling should move to a
    # Redis-backed storage once REDIS_URL is wired up.
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(ErrorHandlingMiddleware())
    dp.update.outer_middleware(DbSessionMiddleware())
    # Must run after DbSessionMiddleware — it needs `session` in data.
    dp.update.outer_middleware(EnsureUserMiddleware())
    # Must run after EnsureUserMiddleware — it needs `user` in data.
    dp.update.outer_middleware(BanCheckMiddleware())

    # Available to every handler as ordinary parameters.
    dp["anilist_client"] = anilist_client
    dp["jikan_client"] = jikan_client
    dp["kitsu_client"] = kitsu_client

    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(anime_extras.router)
    dp.include_router(library.router)
    dp.include_router(profile.router)
    dp.include_router(discovery.router)
    dp.include_router(admin.router)

    logger.info(
        "dispatcher_built",
        extra={
            "routers": [
                "start", "search", "anime_extras", "library", "profile", "discovery", "admin",
            ]
        },
    )
    return dp
