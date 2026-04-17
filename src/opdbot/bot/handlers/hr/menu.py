from aiogram import F, Router
from aiogram.types import Message

from opdbot.bot.keyboards.hr import applications_filter_keyboard
from opdbot.db.models import UserRole

router = Router(name="hr_menu")


@router.message(F.text == "📋 Заявки")
async def hr_applications_menu(message: Message, role: UserRole) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return
    await message.answer("Фильтр заявок:", reply_markup=applications_filter_keyboard())
