import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from opdbot.bot.handlers.candidate import (
    docs,
    feedback,
    onboarding,
    scheduling,
    status,
)
from opdbot.bot.handlers.common import router as common_router
from opdbot.bot.handlers.hr import (
    applications,
    catalog,
    documents_gen,
    menu,
    review,
    slots,
)
from opdbot.bot.middlewares.auth import RoleMiddleware
from opdbot.bot.middlewares.db import DbSessionMiddleware
from opdbot.config import settings
from opdbot.db.base import engine
from opdbot.db.models import Base
from opdbot.logging import setup_logging


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main() -> None:
    setup_logging()
    logger.info("Starting opdbot...")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Middlewares (order matters: db first, then auth)
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(RoleMiddleware())

    # Routers
    dp.include_router(common_router)
    dp.include_router(onboarding.router)
    dp.include_router(docs.router)
    dp.include_router(scheduling.router)
    dp.include_router(status.router)
    dp.include_router(feedback.router)
    dp.include_router(menu.router)
    dp.include_router(applications.router)
    dp.include_router(review.router)
    dp.include_router(slots.router)
    dp.include_router(catalog.router)
    dp.include_router(documents_gen.router)

    await create_tables()
    logger.info("Database tables ensured.")

    if settings.webhook_url:
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

        webhook_path = "/webhook"
        await bot.set_webhook(settings.webhook_url + webhook_path)
        app = web.Application()
        handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
        handler.register(app, path=webhook_path)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="0.0.0.0", port=8080)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
