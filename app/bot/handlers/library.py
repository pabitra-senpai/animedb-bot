"""
/watchlist, /favorites, /history commands, their pagination callbacks,
and the watchlist/favorite toggle + rating callbacks that live on the
anime detail card.

Callback data scheme:
  wl:page:<page> / fav:page:<page> / hist:page:<page>  -> paginate that list
  wl:toggle:<anime_id>:<origin>                         -> toggle watchlist
  fav:toggle:<anime_id>:<origin>                        -> toggle favorite
  rate:menu:<anime_id>:<origin>                         -> show 1-10 picker
  rate:set:<anime_id>:<rating>:<origin>                 -> set rating
  rate:clear:<anime_id>:<origin>                        -> clear rating
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.search import refresh_anime_detail_message
from app.db.models import Anime, User
from app.db.repositories.library_repository import (
    clear_rating,
    get_rating,
    list_favorites,
    list_history,
    list_watchlist,
    set_rating,
    toggle_favorite,
    toggle_watchlist,
)
from app.renderers.library_renderer import (
    LIBRARY_PER_PAGE,
    build_library_list_keyboard,
    build_library_list_text,
)
from app.renderers.rating_renderer import build_rating_menu_keyboard, build_rating_menu_text

router = Router(name="library")

_LIST_FN = {"wl": list_watchlist, "fav": list_favorites, "hist": list_history}


async def _render_library_page(session: AsyncSession, user: User, kind: str, page: int) -> tuple[str, object]:
    items, has_next = await _LIST_FN[kind](session, user.id, page, LIBRARY_PER_PAGE)
    text = build_library_list_text(kind, items, page)
    keyboard = build_library_list_keyboard(kind, items, page, has_next)
    return text, keyboard


@router.message(Command("watchlist"))
async def cmd_watchlist(message: Message, session: AsyncSession, user: User) -> None:
    text, keyboard = await _render_library_page(session, user, "wl", 1)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, session: AsyncSession, user: User) -> None:
    text, keyboard = await _render_library_page(session, user, "fav", 1)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("history"))
async def cmd_history(message: Message, session: AsyncSession, user: User) -> None:
    text, keyboard = await _render_library_page(session, user, "hist", 1)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("wl:page:"))
@router.callback_query(F.data.startswith("fav:page:"))
@router.callback_query(F.data.startswith("hist:page:"))
async def on_library_page(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    kind, _, page_str = callback.data.split(":")
    text, keyboard = await _render_library_page(session, user, kind, int(page_str))
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def _get_anime_or_alert(callback: CallbackQuery, session: AsyncSession, anime_id: int) -> Anime | None:
    anime = await session.get(Anime, anime_id)
    if anime is None:
        await callback.answer("This anime is no longer available.", show_alert=True)
    return anime


def _parse_origin(origin: str) -> int | None:
    return int(origin) if origin != "-" else None


@router.callback_query(F.data.startswith("wl:toggle:"))
async def on_toggle_watchlist(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    now_in = await toggle_watchlist(session, user.id, anime.id)
    await refresh_anime_detail_message(callback.message, anime, session, user, _parse_origin(origin))
    await callback.answer("Added to watchlist ✅" if now_in else "Removed from watchlist")


@router.callback_query(F.data.startswith("fav:toggle:"))
async def on_toggle_favorite(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    now_fav = await toggle_favorite(session, user.id, anime.id)
    await refresh_anime_detail_message(callback.message, anime, session, user, _parse_origin(origin))
    await callback.answer("Added to favorites ❤️" if now_fav else "Removed from favorites")


@router.callback_query(F.data.startswith("rate:menu:"))
async def on_rating_menu(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    current_rating = await get_rating(session, user.id, anime.id)
    text = build_rating_menu_text(anime.title, current_rating)
    keyboard = build_rating_menu_keyboard(anime.id, origin, current_rating)

    if callback.message.photo is not None:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("rate:set:"))
async def on_rating_set(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, rating_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    await set_rating(session, user.id, anime.id, int(rating_str))
    await refresh_anime_detail_message(callback.message, anime, session, user, _parse_origin(origin))
    await callback.answer(f"Rated {rating_str}/10 ⭐")


@router.callback_query(F.data.startswith("rate:clear:"))
async def on_rating_clear(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    await clear_rating(session, user.id, anime.id)
    await refresh_anime_detail_message(callback.message, anime, session, user, _parse_origin(origin))
    await callback.answer("Rating cleared")
