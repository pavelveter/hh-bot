# ruff: noqa: E402

import asyncio
import os
import warnings
from urllib.parse import urlparse

warnings.filterwarnings(
    "ignore",
    message=r'Field "model_custom_emoji_id" has conflict with protected namespace "model_"',
    category=UserWarning,
    module=r"pydantic\._internal\._fields",
)

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.config import settings
from bot.db.database import close_database, init_database
from bot.handlers import register_all_handlers
from bot.services.hh_service import hh_service
from bot.services.openai_service import openai_service
from bot.utils.logging import get_logger
from bot.utils.scheduler import cleanup_scheduler, setup_scheduler

logger = get_logger(__name__)


async def on_startup(bot: Bot):
    os.makedirs("logs", exist_ok=True)
    logger.info("Starting HH Bot...")

    # Database
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"DB init failed: {e}")

    # HH API client
    try:
        await hh_service.init_session()
        logger.info("HH service ready")
    except Exception as e:
        logger.error(f"HH service init failed: {e}")

    # OpenAI client
    try:
        await openai_service.init_service()
        logger.info("OpenAI service ready")
    except Exception as e:
        logger.error(f"OpenAI init failed: {e}")

    # Scheduler
    try:
        await setup_scheduler(bot)
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler init failed: {e}")


async def on_shutdown(bot: Bot):
    logger.info("Shutting down bot...")

    try:
        await cleanup_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")

    try:
        await hh_service.close_session()
        logger.info("HH client closed")
    except Exception as e:
        logger.error(f"Error closing hh: {e}")

    try:
        await close_database()
        logger.info("DB closed")
    except Exception as e:
        logger.error(f"Error closing DB: {e}")

    # Remove webhook in prod
    if settings.ENV.lower() == "prod":
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted")
        except Exception as e:
            logger.error(f"Failed to delete webhook: {e}")


async def run_webhook(bot: Bot, dp: Dispatcher):
    if not settings.WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is not configured for prod environment")

    parsed = urlparse(settings.WEBHOOK_URL)
    webhook_path = parsed.path or "/webhook"

    app = web.Application()
    SimpleRequestHandler(dp, bot).register(app, path=webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.WEBAPP_HOST, port=settings.WEBAPP_PORT)
    await site.start()
    logger.info(
        f"Webhook server started at {settings.WEBAPP_HOST}:{settings.WEBAPP_PORT}{webhook_path}"
    )

    await bot.set_webhook(
        settings.WEBHOOK_URL,
        secret_token=settings.WEBHOOK_SECRET,
        drop_pending_updates=True,
    )
    logger.success(f"Webhook set to {settings.WEBHOOK_URL}")

    try:
        await asyncio.Event().wait()
    finally:
        try:
            await runner.cleanup()
        except Exception as e:
            logger.error(f"Failed to cleanup webhook runner: {e}")


async def main():
    bot = Bot(token=settings.TG_BOT_API_KEY)
    dp = Dispatcher()

    register_all_handlers(dp)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Webhook mode for prod, polling otherwise
    if settings.ENV.lower() == "prod":
        await run_webhook(bot, dp)
    else:
        # Local/dev runs use polling; remove an old webhook if it is still set.
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook removed for polling mode")
        except Exception as e:
            logger.warning(f"Failed to remove webhook before polling: {e}")
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
