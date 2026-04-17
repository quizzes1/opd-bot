import asyncio
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from loguru import logger

CAPTION_LIMIT = 1024


async def notify_user(
    bot: Bot, tg_id: int, text: str, document: Any = None, _retried: bool = False
) -> bool:
    try:
        if document is not None:
            if len(text) <= CAPTION_LIMIT:
                await bot.send_document(tg_id, document, caption=text, parse_mode="HTML")
            else:
                await bot.send_message(tg_id, text, parse_mode="HTML")
                await bot.send_document(tg_id, document)
        else:
            await bot.send_message(tg_id, text, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.warning("Cannot send message to {}: bot blocked", tg_id)
        return False
    except TelegramRetryAfter as e:
        if _retried:
            logger.error("RetryAfter x2 for {}, giving up", tg_id)
            return False
        logger.warning("RetryAfter {}s for {}, waiting", e.retry_after, tg_id)
        await asyncio.sleep(e.retry_after)
        return await notify_user(bot, tg_id, text, document, _retried=True)
    except Exception as e:
        logger.error("Failed to notify {}: {}", tg_id, e)
        return False


async def notify_staff_pool(bot: Bot, tg_ids: list[int], text: str) -> None:
    sem = asyncio.Semaphore(20)

    async def _one(tg_id: int) -> None:
        async with sem:
            await notify_user(bot, tg_id, text)

    await asyncio.gather(*(_one(x) for x in tg_ids), return_exceptions=True)
