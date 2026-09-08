"""
/trending, /popular, /top (/toprated), /airing, /upcoming, /seasonal,
/genres — discovery browsing, all backed by AniList sort/filter queries
(no search string involved). Every result is upserted into the DB same
as search results, so detail cards opened from here are fully cached.

Callback data scheme:
  disc:<kind>:page:<page>      -> re-render that browse list at <page>
  dgen:<genre>:<page>          -> browse a specific genre at <page>
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.renderers.discovery_renderer import (
    DISCOVERY_PER_PAGE,
    build_discovery_keyboard,
    build_discovery_text,
    build_genre_menu_keyboard,
)
from app.services.anilist_client import AniListClient
from app.services.discovery_service import (
    KNOWN_GENRES,
    get_airing,
    get_by_genre,
    get_popular,
    get_seasonal,
    get_top_rated,
    get_trending,
    get_upcoming,
)

router = Router(name="discovery")

_TITLES = {
    "trend": "🔥 Trending Now",
    "pop": "🌟 Most Popular",
    "top": "🏆 Top Rated",
    "air": "📡 Currently Airing",
    "up": "🕒 Upcoming",
}

_FETCHERS = {
    "trend": get_trending,
    "pop": get_popular,
    "top": get_top_rated,
    "air": get_airing,
    "up": get_upcoming,
}


async def _render_and_send(message: Message, session, anilist_client, kind: str, page: int) -> None:
    results, has_next = await _FETCHERS[kind](session, anilist_client, page=page, per_page=DISCOVERY_PER_PAGE)
    text = build_discovery_text(_TITLES[kind], results, page)
    keyboard = build_discovery_keyboard(results, page, has_next, page_callback_prefix=f"disc:{kind}:page:")
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("trending"))
async def cmd_trending(message: Message, session: AsyncSession, anilist_client: AniListClient) -> None:
    await _render_and_send(message, session, anilist_client, "trend", 1)


@router.message(Command("popular"))
async def cmd_popular(message: Message, session: AsyncSession, anilist_client: AniListClient) -> None:
    await _render_and_send(message, session, anilist_client, "pop", 1)


@router.message(Command(commands=["top", "toprated"]))
async def cmd_top_rated(message: Message, session: AsyncSession, anilist_client: AniListClient) -> None:
    await _render_and_send(message, session, anilist_client, "top", 1)


@router.message(Command("airing"))
async def cmd_airing(message: Message, session: AsyncSession, anilist_client: AniListClient) -> None:
    await _render_and_send(message, session, anilist_client, "air", 1)


@router.message(Command("upcoming"))
async def cmd_upcoming(message: Message, session: AsyncSession, anilist_client: AniListClient) -> None:
    await _render_and_send(message, session, anilist_client, "up", 1)


@router.callback_query(F.data.startswith("disc:"))
async def on_discovery_page(callback: CallbackQuery, session: AsyncSession, anilist_client: AniListClient) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, kind, _, page_str = callback.data.split(":")
    results, has_next = await _FETCHERS[kind](
        session, anilist_client, page=int(page_str), per_page=DISCOVERY_PER_PAGE
    )
    text = build_discovery_text(_TITLES[kind], results, int(page_str))
    keyboard = build_discovery_keyboard(
        results, int(page_str), has_next, page_callback_prefix=f"disc:{kind}:page:"
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(Command("seasonal"))
async def cmd_seasonal(message: Message, session: AsyncSession, anilist_client: AniListClient) -> None:
    results, has_next, season, year = await get_seasonal(session, anilist_client, page=1, per_page=DISCOVERY_PER_PAGE)
    title = f"🗓️ {season.title()} {year}"
    text = build_discovery_text(title, results, 1)
    keyboard = build_discovery_keyboard(
        results, 1, has_next, page_callback_prefix=f"disc:season:{season}:{year}:page:"
    )
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("disc:season:"))
async def on_seasonal_page(callback: CallbackQuery, session: AsyncSession, anilist_client: AniListClient) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, season, year_str, _, page_str = callback.data.split(":")
    results, has_next, _, _ = await get_seasonal(
        session, anilist_client, season=season, season_year=int(year_str), page=int(page_str), per_page=DISCOVERY_PER_PAGE
    )
    title = f"🗓️ {season.title()} {year_str}"
    text = build_discovery_text(title, results, int(page_str))
    keyboard = build_discovery_keyboard(
        results, int(page_str), has_next, page_callback_prefix=f"disc:season:{season}:{year_str}:page:"
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(Command("genres"))
async def cmd_genres(message: Message) -> None:
    await message.answer("🏷️ <b>Browse by Genre</b>", reply_markup=build_genre_menu_keyboard(KNOWN_GENRES))


@router.callback_query(F.data.startswith("dgen:"))
async def on_genre_page(callback: CallbackQuery, session: AsyncSession, anilist_client: AniListClient) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, genre, page_str = callback.data.split(":")
    page = int(page_str)
    results, has_next = await get_by_genre(session, anilist_client, genre, page=page, per_page=DISCOVERY_PER_PAGE)
    text = build_discovery_text(f"🏷️ {genre}", results, page)
    keyboard = build_discovery_keyboard(results, page, has_next, page_callback_prefix=f"dgen:{genre}:")

    if callback.message.text is not None:
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()
