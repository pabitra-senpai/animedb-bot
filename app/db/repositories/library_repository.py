"""
Library repository: watchlist, favorites, history, and ratings CRUD.
Each function is a small, direct operation — no orchestration/caching
layer needed here, unlike the AniList-backed services.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserFavorite, UserHistory, UserRating, UserWatchlist


# --- Watchlist ---

async def is_in_watchlist(session: AsyncSession, user_id: int, anime_id: int) -> bool:
    result = await session.execute(
        select(UserWatchlist).where(UserWatchlist.user_id == user_id, UserWatchlist.anime_id == anime_id)
    )
    return result.scalar_one_or_none() is not None


async def toggle_watchlist(session: AsyncSession, user_id: int, anime_id: int) -> bool:
    """Returns True if the anime is now in the watchlist, False if it was removed."""
    result = await session.execute(
        select(UserWatchlist).where(UserWatchlist.user_id == user_id, UserWatchlist.anime_id == anime_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        return False
    session.add(UserWatchlist(user_id=user_id, anime_id=anime_id))
    return True


async def list_watchlist(
    session: AsyncSession, user_id: int, page: int, per_page: int
) -> tuple[list[UserWatchlist], bool]:
    offset = (page - 1) * per_page
    result = await session.execute(
        select(UserWatchlist)
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.added_at.desc())
        .offset(offset)
        .limit(per_page + 1)
    )
    rows = list(result.scalars().all())
    has_next = len(rows) > per_page
    return rows[:per_page], has_next


# --- Favorites ---

async def is_favorite(session: AsyncSession, user_id: int, anime_id: int) -> bool:
    result = await session.execute(
        select(UserFavorite).where(UserFavorite.user_id == user_id, UserFavorite.anime_id == anime_id)
    )
    return result.scalar_one_or_none() is not None


async def toggle_favorite(session: AsyncSession, user_id: int, anime_id: int) -> bool:
    """Returns True if the anime is now a favorite, False if it was removed."""
    result = await session.execute(
        select(UserFavorite).where(UserFavorite.user_id == user_id, UserFavorite.anime_id == anime_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        await session.delete(existing)
        return False
    session.add(UserFavorite(user_id=user_id, anime_id=anime_id))
    return True


async def list_favorites(
    session: AsyncSession, user_id: int, page: int, per_page: int
) -> tuple[list[UserFavorite], bool]:
    offset = (page - 1) * per_page
    result = await session.execute(
        select(UserFavorite)
        .where(UserFavorite.user_id == user_id)
        .order_by(UserFavorite.added_at.desc())
        .offset(offset)
        .limit(per_page + 1)
    )
    rows = list(result.scalars().all())
    has_next = len(rows) > per_page
    return rows[:per_page], has_next


# --- History ---

async def record_history(session: AsyncSession, user_id: int, anime_id: int) -> None:
    result = await session.execute(
        select(UserHistory).where(UserHistory.user_id == user_id, UserHistory.anime_id == anime_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.viewed_at = datetime.now(timezone.utc)
    else:
        session.add(UserHistory(user_id=user_id, anime_id=anime_id))


async def list_history(
    session: AsyncSession, user_id: int, page: int, per_page: int
) -> tuple[list[UserHistory], bool]:
    offset = (page - 1) * per_page
    result = await session.execute(
        select(UserHistory)
        .where(UserHistory.user_id == user_id)
        .order_by(UserHistory.viewed_at.desc())
        .offset(offset)
        .limit(per_page + 1)
    )
    rows = list(result.scalars().all())
    has_next = len(rows) > per_page
    return rows[:per_page], has_next


# --- Ratings ---

async def get_rating(session: AsyncSession, user_id: int, anime_id: int) -> int | None:
    result = await session.execute(
        select(UserRating).where(UserRating.user_id == user_id, UserRating.anime_id == anime_id)
    )
    rating = result.scalar_one_or_none()
    return rating.rating if rating else None


async def set_rating(session: AsyncSession, user_id: int, anime_id: int, rating: int) -> None:
    if not 1 <= rating <= 10:
        raise ValueError("Rating must be between 1 and 10.")
    result = await session.execute(
        select(UserRating).where(UserRating.user_id == user_id, UserRating.anime_id == anime_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.rating = rating
        existing.rated_at = datetime.now(timezone.utc)
    else:
        session.add(UserRating(user_id=user_id, anime_id=anime_id, rating=rating))


async def clear_rating(session: AsyncSession, user_id: int, anime_id: int) -> bool:
    result = await session.execute(
        select(UserRating).where(UserRating.user_id == user_id, UserRating.anime_id == anime_id)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return False
    await session.delete(existing)
    return True


# --- Profile stats ---

async def get_library_stats(session: AsyncSession, user_id: int) -> dict[str, int]:
    async def _count(model) -> int:
        result = await session.execute(
            select(func.count()).select_from(model).where(model.user_id == user_id)
        )
        return result.scalar_one()

    return {
        "watchlist_count": await _count(UserWatchlist),
        "favorites_count": await _count(UserFavorite),
        "history_count": await _count(UserHistory),
        "ratings_count": await _count(UserRating),
    }
