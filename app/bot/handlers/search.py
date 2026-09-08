"""
/search command + the callback handlers for result pagination and
viewing an anime's detail card.

Callback data scheme (kept short — Telegram caps callback_data at 64
bytes):
  srch:p:<page>            -> re-render search results at <page>
                               (query text comes from FSM state, not the
                               callback payload, so it never has to fit)
  anime:v:<anime_id>:<page> -> show anime <anime_id>'s detail card;
                               <page> remembers where to go "back" to
  anime:back:<page>         -> re-render search results at <page>
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, User
from app.db.repositories.anime_repository import get_genre_names, get_studio_names
from app.db.repositories.library_repository import is_favorite, is_in_watchlist, get_rating, record_history
from app.renderers.anime_renderer import (
    PHOTO_CAPTION_LIMIT,
    TEXT_MESSAGE_LIMIT,
    build_anime_detail_text,
    build_anime_keyboard,
)
from app.renderers.search_renderer import (
    RESULTS_PER_PAGE,
    build_search_results_keyboard,
    build_search_results_text,
)
from app.services.anilist_client import AniListClient
from app.services.jikan_client import JikanClient
from app.services.search_service import InvalidSearchQueryError, search_anime

logger = logging.getLogger(__name__)

router = Router(name="search")


async def _run_search_and_render(
    query: str,
    page: int,
    session: AsyncSession,
    anilist_client: AniListClient,
    jikan_client: JikanClient,
) -> tuple[str, object]:
    """Returns (text, keyboard) for a search results page."""
    results = await search_anime(
        session, anilist_client, query, page=page, per_page=RESULTS_PER_PAGE, jikan_client=jikan_client
    )
    text = build_search_results_text(query, page, len(results))
    has_next_page = len(results) >= RESULTS_PER_PAGE
    keyboard = build_search_results_keyboard(results, page, has_next_page)
    return text, keyboard


@router.message(Command("search"))
async def cmd_search(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    anilist_client: AniListClient,
    jikan_client: JikanClient,
) -> None:
    query = (command.args or "").strip()
    if not query:
        await message.answer(
            "Usage: <code>/search &lt;anime title&gt;</code>\nExample: <code>/search One Piece</code>"
        )
        return

    try:
        text, keyboard = await _run_search_and_render(query, 1, session, anilist_client, jikan_client)
    except InvalidSearchQueryError as exc:
        await message.answer(f"⚠️ {exc}")
        return

    await state.update_data(last_search_query=query)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("srch:p:"))
async def on_search_page(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    anilist_client: AniListClient,
    jikan_client: JikanClient,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    page = int(callback.data.split(":")[2])
    data = await state.get_data()
    query = data.get("last_search_query")

    if not query:
        await callback.answer("This search has expired — please run /search again.", show_alert=True)
        return

    try:
        text, keyboard = await _run_search_and_render(query, page, session, anilist_client, jikan_client)
    except InvalidSearchQueryError:
        await callback.answer("That search is no longer valid.", show_alert=True)
        return

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("anime:back:"))
async def on_back_to_results(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    anilist_client: AniListClient,
    jikan_client: JikanClient,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    page = int(callback.data.split(":")[2])
    data = await state.get_data()
    query = data.get("last_search_query")

    if not query:
        await callback.answer("This search has expired — please run /search again.", show_alert=True)
        return

    text, keyboard = await _run_search_and_render(query, page, session, anilist_client, jikan_client)
    # The detail card is a separate message (often a photo) — send fresh
    # rather than trying to edit it back into a results list.
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("anime:v:"))
async def on_view_anime(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, from_page_str = callback.data.split(":")
    anime = await session.get(Anime, int(anime_id_str))

    if anime is None:
        await callback.answer("This anime is no longer available.", show_alert=True)
        return

    from_page = int(from_page_str) if from_page_str != "-" else None
    await send_anime_detail(callback.message, anime, session, user, from_page=from_page)
    await callback.answer()


async def send_anime_detail(
    target: Message,
    anime: Anime,
    session: AsyncSession,
    user: User,
    from_page: int | None = None,
) -> None:
    """Shared by the search-results callback and /start's deep-link handler."""
    await record_history(session, user.id, anime.id)
    caption, text, keyboard = await _build_detail_content(session, anime, user, from_page)

    if anime.poster_url:
        try:
            await target.answer_photo(photo=anime.poster_url, caption=caption, reply_markup=keyboard)
            return
        except Exception:
            logger.exception("failed_to_send_poster_photo_falling_back_to_text", extra={"anime_id": anime.id})

    await target.answer(text, reply_markup=keyboard)


async def refresh_anime_detail_message(
    message: Message,
    anime: Anime,
    session: AsyncSession,
    user: User,
    from_page: int | None,
) -> None:
    """Updates an existing detail card in place (e.g. after a watchlist
    toggle or rating change) rather than sending a new message."""
    caption, text, keyboard = await _build_detail_content(session, anime, user, from_page)

    if message.photo is not None:
        await message.edit_caption(caption=caption, reply_markup=keyboard)
    else:
        await message.edit_text(text, reply_markup=keyboard)


async def _build_detail_content(
    session: AsyncSession, anime: Anime, user: User, from_page: int | None
) -> tuple[str, str, object]:
    genre_names = await get_genre_names(session, anime.id)
    studio_names = await get_studio_names(session, anime.id)

    in_watchlist = await is_in_watchlist(session, user.id, anime.id)
    favorited = await is_favorite(session, user.id, anime.id)
    current_rating = await get_rating(session, user.id, anime.id)

    keyboard = build_anime_keyboard(
        anime,
        from_page=from_page,
        in_watchlist=in_watchlist,
        is_favorite=favorited,
        current_rating=current_rating,
    )
    caption = build_anime_detail_text(
        anime, PHOTO_CAPTION_LIMIT, genre_names=genre_names, studio_names=studio_names
    )
    text = build_anime_detail_text(
        anime, TEXT_MESSAGE_LIMIT, genre_names=genre_names, studio_names=studio_names
    )
    return caption, text, keyboard
