"""
Callback handlers for the "📺 Episodes", "🎭 Characters", "👥 Staff"
buttons on an anime's detail card.

Callback data scheme: <kind>:list:<anime_id>:<page>:<origin>
  - <kind> is one of ep / char / staff
  - <origin> is the search-results page to return to via the anime detail
    card's own "back to results" button ("-" if there wasn't one, e.g.
    when reached via a /start deep link)
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime
from app.renderers.character_renderer import build_character_list_keyboard, build_character_list_text
from app.renderers.episode_renderer import build_episode_list_keyboard, build_episode_list_text
from app.renderers.staff_renderer import build_staff_list_keyboard, build_staff_list_text
from app.services.anilist_client import AniListClient
from app.services.character_service import get_anime_characters_page
from app.services.episode_service import get_episode_page
from app.services.kitsu_client import KitsuClient
from app.services.kitsu_enrichment_service import enrich_episodes_from_kitsu
from app.services.staff_service import get_anime_staff_page

router = Router(name="anime_extras")

_PER_PAGE = 10


async def _get_anime_or_alert(callback: CallbackQuery, session: AsyncSession, anime_id: int) -> Anime | None:
    anime = await session.get(Anime, anime_id)
    if anime is None:
        await callback.answer("This anime is no longer available.", show_alert=True)
    return anime


@router.callback_query(F.data.startswith("ep:list:"))
async def on_episode_list(callback: CallbackQuery, session: AsyncSession, kitsu_client: KitsuClient) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, page_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    page = int(page_str)
    episodes, has_next = await get_episode_page(session, anime, page=page, per_page=_PER_PAGE)

    # Best-effort enrichment: if this page has no titled episodes at all
    # and we've never tried Kitsu for this anime, try once and re-render.
    # Only on page 1 — later pages don't retrigger a fresh attempt.
    if page == 1 and episodes and anime.kitsu_id is None and not any(e.title for e in episodes):
        enriched = await enrich_episodes_from_kitsu(session, kitsu_client, anime)
        if enriched:
            episodes, has_next = await get_episode_page(session, anime, page=page, per_page=_PER_PAGE)

    text = build_episode_list_text(anime.title, episodes, page)
    keyboard = build_episode_list_keyboard(anime.id, page, has_next, origin)

    if _is_editable(callback.message):
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("char:list:"))
async def on_character_list(
    callback: CallbackQuery, session: AsyncSession, anilist_client: AniListClient
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, page_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    page = int(page_str)
    characters, has_next = await get_anime_characters_page(
        session, anilist_client, anime, page=page, per_page=_PER_PAGE
    )
    text = build_character_list_text(anime.title, characters, page)
    keyboard = build_character_list_keyboard(anime.id, page, has_next, origin)

    if _is_editable(callback.message):
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("staff:list:"))
async def on_staff_list(
    callback: CallbackQuery, session: AsyncSession, anilist_client: AniListClient
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    _, _, anime_id_str, page_str, origin = callback.data.split(":")
    anime = await _get_anime_or_alert(callback, session, int(anime_id_str))
    if anime is None:
        return

    page = int(page_str)
    staff, has_next = await get_anime_staff_page(
        session, anilist_client, anime, page=page, per_page=_PER_PAGE
    )
    text = build_staff_list_text(anime.title, staff, page)
    keyboard = build_staff_list_keyboard(anime.id, page, has_next, origin)

    if _is_editable(callback.message):
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


def _is_editable(message: Message) -> bool:
    """These list views are plain text; only edit in place if the message
    we're responding to is itself text (not a photo caption, which
    Telegram won't let us turn into a text message body)."""
    return message.text is not None
