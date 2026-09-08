from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.user_repository import get_or_create_user


@pytest.mark.asyncio
async def test_creates_new_user(session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_user_id=111, first_name="Pabitra", username="pabitra_senpai")
    await session.commit()

    assert user.id is not None
    assert user.telegram_user_id == 111
    assert user.is_admin is False
    assert user.notifications_enabled is True


@pytest.mark.asyncio
async def test_second_call_updates_existing_user_not_duplicate(session: AsyncSession) -> None:
    first = await get_or_create_user(session, telegram_user_id=111, first_name="Pabitra", username="old_handle")
    await session.commit()
    first_id = first.id

    second = await get_or_create_user(session, telegram_user_id=111, first_name="Pabitra", username="new_handle")
    await session.commit()

    assert second.id == first_id
    assert second.username == "new_handle"

    result = await session.execute(select(User).where(User.telegram_user_id == 111))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_last_active_at_is_updated(session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_user_id=222, first_name="X")
    await session.commit()
    assert user.last_active_at is not None


@pytest.mark.asyncio
async def test_admin_id_in_set_gets_is_admin_true(session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_user_id=333, first_name="Admin", admin_ids={333, 444})
    await session.commit()
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_admin_id_not_in_set_gets_is_admin_false(session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_user_id=555, first_name="Regular", admin_ids={333, 444})
    await session.commit()
    assert user.is_admin is False


@pytest.mark.asyncio
async def test_admin_status_revoked_when_removed_from_config(session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_user_id=333, first_name="X", admin_ids={333})
    await session.commit()
    assert user.is_admin is True

    # Config changed — 333 no longer listed as an admin.
    user = await get_or_create_user(session, telegram_user_id=333, first_name="X", admin_ids=set())
    await session.commit()
    assert user.is_admin is False


@pytest.mark.asyncio
async def test_no_admin_ids_arg_leaves_is_admin_unchanged(session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_user_id=333, first_name="X", admin_ids={333})
    await session.commit()
    assert user.is_admin is True

    # Called without admin_ids (e.g. a hypothetical other call site) —
    # should not silently demote an admin.
    user = await get_or_create_user(session, telegram_user_id=333, first_name="X")
    await session.commit()
    assert user.is_admin is True
