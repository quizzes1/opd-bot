from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import FSInputFile
from loguru import logger


async def notify_user(bot: Bot, tg_id: int, text: str, document: Any = None) -> bool:
    try:
        await bot.send_message(tg_id, text, parse_mode="HTML")
        if document is not None:
            await bot.send_document(tg_id, document)
        return True
    except TelegramForbiddenError:
        logger.warning("Cannot send message to {}: bot blocked", tg_id)
        return False
    except Exception as e:
        logger.error("Failed to notify {}: {}", tg_id, e)
        return False
