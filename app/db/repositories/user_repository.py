"""
User repository: the single place that creates/updates User rows from
Telegram's `from_user` data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_or_create_user(
    session: AsyncSession,
    telegram_user_id: int,
    first_name: str,
    username: str | None = None,
    last_name: str | None = None,
    language_code: str | None = None,
    admin_ids: set[int] | None = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    is_admin = telegram_user_id in admin_ids if admin_ids is not None else False

    if user is None:
        user = User(
            telegram_user_id=telegram_user_id,
            first_name=first_name,
            username=username,
            last_name=last_name,
            language_code=language_code,
            last_active_at=now,
            is_admin=is_admin,
        )
        session.add(user)
        await session.flush()
    else:
        user.first_name = first_name
        user.username = username
        user.last_name = last_name
        user.language_code = language_code
        user.last_active_at = now
        # ADMIN_IDS in config is the source of truth — keeps admin status
        # in sync even if it's edited after a user's first interaction.
        if admin_ids is not None:
            user.is_admin = is_admin

    return user
