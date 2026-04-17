from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from opdbot.db.models import Goal


def goals_keyboard(goals: list[Goal]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for goal in goals:
        builder.button(text=goal.title, callback_data=f"goal:{goal.id}")
    builder.adjust(1)
    return builder.as_markup()
