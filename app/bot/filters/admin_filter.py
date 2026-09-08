from __future__ import annotations

from aiogram.filters import BaseFilter

from app.db.models import User


class IsAdmin(BaseFilter):
    async def __call__(self, event, user: User) -> bool:
        return user.is_admin
