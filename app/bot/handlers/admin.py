"""
Admin-only commands. All gated by the IsAdmin filter, which checks
`user.is_admin` (set from ADMIN_IDS in config — see user_repository).
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin_filter import IsAdmin
from app.db.repositories.admin_repository import (
    get_active_user_telegram_ids,
    get_bot_stats,
    set_user_banned,
)
from app.renderers.admin_renderer import (
    build_admin_help_text,
    build_broadcast_confirm_keyboard,
    build_broadcast_preview_text,
    build_broadcast_result_text,
    build_stats_text,
    build_sync_result_text,
)
from app.services.anilist_client import AniListClient
from app.services.broadcast_service import broadcast_message
from app.services.sync_job import sync_stale_anime_once

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(build_admin_help_text())


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    stats = await get_bot_stats(session)
    await message.answer(build_stats_text(stats))


@router.message(Command("broadcast"))
async def cmd_broadcast(
    message: Message, command: CommandObject, session: AsyncSession, state: FSMContext
) -> None:
    text = (command.args or "").strip()
    if not text:
        await message.answer("Usage: <code>/broadcast &lt;message&gt;</code>")
        return

    recipient_ids = await get_active_user_telegram_ids(session)
    await state.update_data(pending_broadcast_text=text, pending_broadcast_count=len(recipient_ids))

    await message.answer(
        build_broadcast_preview_text(text, len(recipient_ids)),
        reply_markup=build_broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "bcast:confirm")
async def on_broadcast_confirm(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    data = await state.get_data()
    text = data.get("pending_broadcast_text")
    if not text:
        await callback.answer("This broadcast has expired.", show_alert=True)
        return

    await callback.message.edit_text("📢 Sending broadcast…")
    await callback.answer()

    recipient_ids = await get_active_user_telegram_ids(session)
    sent, failed = await broadcast_message(bot, recipient_ids, text)

    await state.update_data(pending_broadcast_text=None, pending_broadcast_count=None)
    await callback.message.edit_text(build_broadcast_result_text(sent, failed))


@router.callback_query(F.data == "bcast:cancel")
async def on_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.update_data(pending_broadcast_text=None, pending_broadcast_count=None)
    await callback.message.edit_text("❌ Broadcast cancelled.")
    await callback.answer()


@router.message(Command("sync"))
async def cmd_sync(message: Message, anilist_client: AniListClient) -> None:
    await message.answer("🔄 Running a sync pass now…")
    synced, failed = await sync_stale_anime_once(anilist_client, ttl_seconds=0, batch_size=20)
    await message.answer(build_sync_result_text(synced, failed))


@router.message(Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, session: AsyncSession) -> None:
    target_id = _parse_target_id(command.args)
    if target_id is None:
        await message.answer("Usage: <code>/ban &lt;telegram_user_id&gt;</code>")
        return

    user = await set_user_banned(session, target_id, banned=True)
    if user is None:
        await message.answer(f"No user found with ID {target_id}.")
        return
    await message.answer(f"🚫 Banned user {target_id}.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, session: AsyncSession) -> None:
    target_id = _parse_target_id(command.args)
    if target_id is None:
        await message.answer("Usage: <code>/unban &lt;telegram_user_id&gt;</code>")
        return

    user = await set_user_banned(session, target_id, banned=False)
    if user is None:
        await message.answer(f"No user found with ID {target_id}.")
        return
    await message.answer(f"✅ Unbanned user {target_id}.")


def _parse_target_id(args: str | None) -> int | None:
    if not args:
        return None
    try:
        return int(args.strip())
    except ValueError:
        return None
