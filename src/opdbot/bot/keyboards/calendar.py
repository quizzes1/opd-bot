from datetime import datetime

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from opdbot.db.models import Slot


def slots_keyboard(slots: list[Slot], kind: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        dt_str = slot.starts_at.strftime("%d.%m %H:%M")
        free = slot.capacity - slot.booked_count
        builder.button(
            text=f"{dt_str} (мест: {free})",
            callback_data=f"slot:{kind}:{slot.id}",
        )
    builder.adjust(1)
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()
