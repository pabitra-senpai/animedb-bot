from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, User
from app.db.repositories.admin_repository import (
    get_active_user_telegram_ids,
    get_bot_stats,
    set_user_banned,
)
from app.db.repositories.library_repository import toggle_favorite, toggle_watchlist


@pytest.mark.asyncio
async def test_get_bot_stats(session: AsyncSession) -> None:
    u1 = User(telegram_user_id=1, first_name="A", is_admin=True)
    u2 = User(telegram_user_id=2, first_name="B", is_banned=True)
    u3 = User(telegram_user_id=3, first_name="C")
    anime = Anime(title="One Piece")
    session.add_all([u1, u2, u3, anime])
    await session.flush()

    await toggle_watchlist(session, u3.id, anime.id)
    await toggle_favorite(session, u3.id, anime.id)
    await session.commit()

    stats = await get_bot_stats(session)
    assert stats["total_users"] == 3
    assert stats["admin_users"] == 1
    assert stats["banned_users"] == 1
    assert stats["total_anime"] == 1
    assert stats["total_watchlist_entries"] == 1
    assert stats["total_favorites"] == 1


@pytest.mark.asyncio
async def test_get_active_user_telegram_ids_excludes_banned(session: AsyncSession) -> None:
    session.add_all(
        [
            User(telegram_user_id=1, first_name="A"),
            User(telegram_user_id=2, first_name="B", is_banned=True),
            User(telegram_user_id=3, first_name="C"),
        ]
    )
    await session.commit()

    active_ids = await get_active_user_telegram_ids(session)
    assert sorted(active_ids) == [1, 3]


@pytest.mark.asyncio
async def test_set_user_banned_toggles(session: AsyncSession) -> None:
    session.add(User(telegram_user_id=1, first_name="A"))
    await session.commit()

    user = await set_user_banned(session, 1, banned=True)
    await session.commit()
    assert user.is_banned is True

    user = await set_user_banned(session, 1, banned=False)
    await session.commit()
    assert user.is_banned is False


@pytest.mark.asyncio
async def test_set_user_banned_unknown_user_returns_none(session: AsyncSession) -> None:
    result = await set_user_banned(session, 999999, banned=True)
    assert result is None
