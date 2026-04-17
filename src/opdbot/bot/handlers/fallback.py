from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from opdbot.bot import texts

router = Router(name="fallback")


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(texts.CANCELLED)
    await callback.answer()


@router.callback_query()
async def cb_unknown(callback: CallbackQuery) -> None:
    await callback.answer("Неизвестная команда. Нажмите /start.")


@router.message()
async def msg_unknown(message: Message) -> None:
    await message.answer(texts.HELP_TEXT)
