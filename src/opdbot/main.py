import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiohttp import web
from loguru import logger

from opdbot.bot.handlers.candidate import (
    docs,
    feedback,
    onboarding,
    scheduling,
    status,
)
from opdbot.bot.handlers.common import router as common_router
from opdbot.bot.handlers.fallback import router as fallback_router
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
from opdbot.logging import setup_logging


def build_storage() -> BaseStorage:
    if settings.redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage

            storage: BaseStorage = RedisStorage.from_url(settings.redis_url)
            logger.info("Using RedisStorage for FSM")
            return storage
        except ImportError:
            logger.warning("redis is not installed, falling back to MemoryStorage")
    return MemoryStorage()


def register_routers(dp: Dispatcher) -> None:
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
    dp.include_router(fallback_router)


async def setup_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Запустить / перезапустить бота"),
        BotCommand(command="help", description="Справка и список команд"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ]
    if settings.dev_mode:
        commands.append(
            BotCommand(command="switch_role", description="DEV: сменить роль")
        )
    await bot.set_my_commands(commands)


async def _health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    webhook_path = "/webhook"
    await bot.set_webhook(settings.webhook_url.rstrip("/") + webhook_path)

    app = web.Application()
    app.router.add_get("/health", _health)
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)
    await site.start()
    logger.info("Webhook site started on {}:{}", settings.webhook_host, settings.webhook_port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    setup_logging()
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN is required. Set it in .env")

    logger.info("Starting opdbot...")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=build_storage())

    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(RoleMiddleware())

    register_routers(dp)
    await setup_bot_commands(bot)

    if settings.webhook_url:
        await run_webhook(bot, dp)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
