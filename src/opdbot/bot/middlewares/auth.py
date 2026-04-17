from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

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
        role: UserRole = UserRole.candidate
        if tg_user is not None:
            session: AsyncSession | None = data.get("session")
            if session is not None:
                user = await get_user_by_tg_id(session, tg_user.id)
                if user is not None:
                    role = user.role
        data["role"] = role
        return await handler(event, data)
