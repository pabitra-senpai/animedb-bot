"""
Admin repository: bot-wide stats, the active-user list broadcast sends
to, and ban/unban. Kept separate from library_repository (which is
per-user CRUD) since these are cross-user, admin-only operations.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Anime,
    User,
    UserFavorite,
    UserHistory,
    UserRating,
    UserWatchlist,
)


async def get_bot_stats(session: AsyncSession) -> dict[str, int]:
    async def _count(model) -> int:
        result = await session.execute(select(func.count()).select_from(model))
        return result.scalar_one()

    async def _count_where(model, *where) -> int:
        result = await session.execute(select(func.count()).select_from(model).where(*where))
        return result.scalar_one()

    return {
        "total_users": await _count(User),
        "banned_users": await _count_where(User, User.is_banned.is_(True)),
        "admin_users": await _count_where(User, User.is_admin.is_(True)),
        "total_anime": await _count(Anime),
        "total_watchlist_entries": await _count(UserWatchlist),
        "total_favorites": await _count(UserFavorite),
        "total_history_entries": await _count(UserHistory),
        "total_ratings": await _count(UserRating),
    }


async def get_active_user_telegram_ids(session: AsyncSession) -> list[int]:
    """Non-banned users, for broadcast targeting."""
    result = await session.execute(
        select(User.telegram_user_id).where(User.is_banned.is_(False))
    )
    return list(result.scalars().all())


async def get_user_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    return result.scalar_one_or_none()


async def set_user_banned(session: AsyncSession, telegram_user_id: int, banned: bool) -> User | None:
    user = await get_user_by_telegram_id(session, telegram_user_id)
    if user is None:
        return None
    user.is_banned = banned
    return user
