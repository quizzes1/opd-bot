from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from opdbot.config import settings
from opdbot.db.models import UserRole
from opdbot.db.repo.users import get_user_by_tg_id


class RoleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None and isinstance(event, Update):
            tg_user = event.event.from_user if hasattr(event.event, "from_user") else None

        role: UserRole = UserRole.candidate
        if tg_user:
            tg_id = tg_user.id
            if tg_id in settings.superadmin_tg_ids:
                role = UserRole.admin
            else:
                session: AsyncSession | None = data.get("session")
                if session:
                    user = await get_user_by_tg_id(session, tg_id)
                    if user:
                        role = user.role

        data["role"] = role
        return await handler(event, data)
