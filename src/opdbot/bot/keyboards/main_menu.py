from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from opdbot.bot import texts


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=texts.BTN_CANCEL_REPLY))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)


def candidate_main_menu(has_active_application: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📋 Мои заявки"))
    if has_active_application:
        builder.row(
            KeyboardButton(text="📅 Записаться на собеседование"),
            KeyboardButton(text="🎓 Записаться на обучение"),
        )
        builder.row(
            KeyboardButton(text="🔄 Изменить документы"),
            KeyboardButton(text="💬 Связаться с HR"),
        )
    else:
        builder.row(KeyboardButton(text="📄 Подать заявку"))
        builder.row(KeyboardButton(text="💬 Связаться с HR"))
    return builder.as_markup(resize_keyboard=True)


def hr_main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📋 Заявки"), KeyboardButton(text="🔍 Поиск"))
    builder.row(KeyboardButton(text="📅 Слоты"), KeyboardButton(text="📂 Каталог документов"))
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()
