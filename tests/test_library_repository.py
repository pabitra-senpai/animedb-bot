from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Anime, User
from app.db.repositories.library_repository import (
    clear_rating,
    get_library_stats,
    get_rating,
    is_favorite,
    is_in_watchlist,
    list_favorites,
    list_history,
    list_watchlist,
    record_history,
    set_rating,
    toggle_favorite,
    toggle_watchlist,
)


async def _make_user_and_anime(session: AsyncSession, n: int = 1) -> tuple[User, list[Anime]]:
    user = User(telegram_user_id=1, first_name="Pabitra")
    session.add(user)
    animes = [Anime(title=f"Anime {i}") for i in range(n)]
    session.add_all(animes)
    await session.flush()
    return user, animes


@pytest.mark.asyncio
async def test_toggle_watchlist_adds_then_removes(session: AsyncSession) -> None:
    user, [anime] = await _make_user_and_anime(session)

    added = await toggle_watchlist(session, user.id, anime.id)
    await session.commit()
    assert added is True
    assert await is_in_watchlist(session, user.id, anime.id) is True

    removed = await toggle_watchlist(session, user.id, anime.id)
    await session.commit()
    assert removed is False
    assert await is_in_watchlist(session, user.id, anime.id) is False


@pytest.mark.asyncio
async def test_watchlist_is_per_user(session: AsyncSession) -> None:
    user1 = User(telegram_user_id=1, first_name="A")
    user2 = User(telegram_user_id=2, first_name="B")
    anime = Anime(title="One Piece")
    session.add_all([user1, user2, anime])
    await session.flush()

    await toggle_watchlist(session, user1.id, anime.id)
    await session.commit()

    assert await is_in_watchlist(session, user1.id, anime.id) is True
    assert await is_in_watchlist(session, user2.id, anime.id) is False


@pytest.mark.asyncio
async def test_list_watchlist_pagination(session: AsyncSession) -> None:
    user, animes = await _make_user_and_anime(session, n=5)
    for a in animes:
        await toggle_watchlist(session, user.id, a.id)
    await session.commit()

    page1, has_next = await list_watchlist(session, user.id, page=1, per_page=3)
    assert len(page1) == 3
    assert has_next is True

    page2, has_next2 = await list_watchlist(session, user.id, page=2, per_page=3)
    assert len(page2) == 2
    assert has_next2 is False


@pytest.mark.asyncio
async def test_toggle_favorite(session: AsyncSession) -> None:
    user, [anime] = await _make_user_and_anime(session)

    assert await toggle_favorite(session, user.id, anime.id) is True
    await session.commit()
    assert await is_favorite(session, user.id, anime.id) is True

    assert await toggle_favorite(session, user.id, anime.id) is False
    await session.commit()
    assert await is_favorite(session, user.id, anime.id) is False


@pytest.mark.asyncio
async def test_record_history_upserts_not_duplicates(session: AsyncSession) -> None:
    user, [anime] = await _make_user_and_anime(session)

    await record_history(session, user.id, anime.id)
    await session.commit()
    first_items, _ = await list_history(session, user.id, page=1, per_page=10)
    assert len(first_items) == 1

    await record_history(session, user.id, anime.id)
    await session.commit()
    second_items, _ = await list_history(session, user.id, page=1, per_page=10)

    assert len(second_items) == 1  # not duplicated
    assert second_items[0].viewed_at is not None


@pytest.mark.asyncio
async def test_set_and_get_rating(session: AsyncSession) -> None:
    user, [anime] = await _make_user_and_anime(session)

    assert await get_rating(session, user.id, anime.id) is None

    await set_rating(session, user.id, anime.id, 8)
    await session.commit()
    assert await get_rating(session, user.id, anime.id) == 8

    await set_rating(session, user.id, anime.id, 10)  # update, not duplicate
    await session.commit()
    assert await get_rating(session, user.id, anime.id) == 10


@pytest.mark.asyncio
async def test_set_rating_rejects_out_of_range(session: AsyncSession) -> None:
    user, [anime] = await _make_user_and_anime(session)

    with pytest.raises(ValueError):
        await set_rating(session, user.id, anime.id, 0)
    with pytest.raises(ValueError):
        await set_rating(session, user.id, anime.id, 11)


@pytest.mark.asyncio
async def test_clear_rating(session: AsyncSession) -> None:
    user, [anime] = await _make_user_and_anime(session)
    await set_rating(session, user.id, anime.id, 7)
    await session.commit()

    cleared = await clear_rating(session, user.id, anime.id)
    await session.commit()
    assert cleared is True
    assert await get_rating(session, user.id, anime.id) is None

    cleared_again = await clear_rating(session, user.id, anime.id)
    assert cleared_again is False


@pytest.mark.asyncio
async def test_get_library_stats(session: AsyncSession) -> None:
    user, animes = await _make_user_and_anime(session, n=3)
    await toggle_watchlist(session, user.id, animes[0].id)
    await toggle_favorite(session, user.id, animes[0].id)
    await toggle_favorite(session, user.id, animes[1].id)
    await record_history(session, user.id, animes[0].id)
    await set_rating(session, user.id, animes[0].id, 9)
    await session.commit()

    stats = await get_library_stats(session, user.id)
    assert stats == {
        "watchlist_count": 1,
        "favorites_count": 2,
        "history_count": 1,
        "ratings_count": 1,
    }
