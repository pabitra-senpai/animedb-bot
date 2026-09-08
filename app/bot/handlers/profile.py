"""
/profile — quick stats summary.
/settings — notification preference toggle.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.library_repository import get_library_stats
from app.renderers.profile_renderer import build_profile_text, build_settings_keyboard, build_settings_text

router = Router(name="profile")


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession, user: User) -> None:
    stats = await get_library_stats(session, user.id)
    await message.answer(build_profile_text(user, stats))


@router.message(Command("settings"))
async def cmd_settings(message: Message, user: User) -> None:
    await message.answer(build_settings_text(user), reply_markup=build_settings_keyboard(user))


@router.callback_query(F.data == "settings:toggle_notifications")
async def on_toggle_notifications(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    user.notifications_enabled = not user.notifications_enabled
    await callback.message.edit_text(build_settings_text(user), reply_markup=build_settings_keyboard(user))
    await callback.answer("Notifications updated")
