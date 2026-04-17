from aiogram import F, Router
from aiogram.types import Message

from opdbot.bot import texts
from opdbot.bot.keyboards.main_menu import hr_main_menu
from opdbot.db.models import UserRole

router = Router(name="hr_menu")


@router.message(F.text == "📋 Заявки")
async def hr_applications_menu(message: Message, role: UserRole) -> None:
    if role not in (UserRole.hr, UserRole.admin):
        return
    from opdbot.bot.keyboards.hr import applications_filter_keyboard
    await message.answer("Фильтр заявок:", reply_markup=applications_filter_keyboard())
