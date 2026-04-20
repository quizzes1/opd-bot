from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from opdbot.db.models import Slot
from opdbot.utils.dates import fmt_datetime


def slots_keyboard(slots: list[Slot], kind: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        dt_str = fmt_datetime(slot.starts_at)
        free = slot.capacity - slot.booked_count
        builder.button(
            text=f"{dt_str} (мест: {free})",
            callback_data=f"slot:{kind}:{slot.id}",
        )
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()
