from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from opdbot.db.models import (
    ACTIVE_STATUSES,
    Application,
    Document,
    DocumentRequirement,
)


def application_card_keyboard(app: Application) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Документы", callback_data=f"hr:docs:{app.id}")
    builder.button(text="📝 Сгенерированные", callback_data=f"hr:gendocs:{app.id}")
    builder.button(text="✅ Принят", callback_data=f"hr:approve:{app.id}")
    builder.button(text="❌ Отказ", callback_data=f"hr:reject:{app.id}")
    builder.button(text="📅 Назначить собеседование", callback_data=f"hr:set_interview:{app.id}")
    builder.button(text="🏥 Отправить на медосмотр", callback_data=f"hr:medical:{app.id}")
    builder.button(text="📋 Запросить документ", callback_data=f"hr:request_doc:{app.id}")
    builder.button(text="💬 Написать кандидату", callback_data=f"hr:message:{app.id}")
    builder.button(text="📄 Сформировать характеристику", callback_data=f"hr:characteristic:{app.id}")
    if app.status in ACTIVE_STATUSES:
        builder.button(text="🗑 Отменить заявку", callback_data=f"hr:cancel_app:{app.id}")
    builder.button(text="◀️ Назад", callback_data="hr:applications")
    builder.adjust(2)
    return builder.as_markup()


def document_actions_keyboard(doc: Document) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Скачать", callback_data=f"hr:dl_doc:{doc.id}")
    builder.button(text="✅ Одобрить", callback_data=f"hr:approve_doc:{doc.id}")
    builder.button(text="❌ Отклонить", callback_data=f"hr:reject_doc:{doc.id}")
    builder.button(text="◀️ Назад", callback_data=f"hr:docs:{doc.application_id}")
    builder.adjust(2)
    return builder.as_markup()


def applications_filter_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Активные", callback_data="hr:filter:active")
    builder.button(text="Все", callback_data="hr:filter:all")
    builder.button(text="На проверке", callback_data="hr:filter:docs_submitted")
    builder.button(text="Собеседование", callback_data="hr:filter:interview_scheduled")
    builder.button(text="Одобрены", callback_data="hr:filter:approved")
    builder.button(text="Отказ", callback_data="hr:filter:rejected")
    builder.adjust(2)
    return builder.as_markup()


def slot_kind_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Собеседование", callback_data="hr:slot_kind:interview")
    builder.button(text="Медосмотр", callback_data="hr:slot_kind:medical")
    builder.button(text="Обучение", callback_data="hr:slot_kind:training")
    builder.adjust(1)
    return builder.as_markup()


def request_doc_keyboard(requirements: list[DocumentRequirement]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for req in requirements:
        builder.button(text=req.title, callback_data=f"hr:req_doc:{req.id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def confirm_keyboard(yes_cb: str, no_cb: str = "cancel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=yes_cb)
    builder.button(text="❌ Нет", callback_data=no_cb)
    return builder.as_markup()
