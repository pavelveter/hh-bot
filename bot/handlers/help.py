"""Handler for /help command"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import UserRepository
from bot.db.database import get_db_session
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)

router = Router()


def register_help_handlers(router_instance: Router):
    """Register help command handlers"""
    try:
        router_instance.include_router(router)
        logger.info("Help handlers registered successfully")
    except Exception as e:
        logger.error(f"Failed to register help handlers: {e}")


@router.message(Command("help"))
async def help_handler(message: Message):
    """Handler for the /help command with comprehensive logging"""
    user_id = str(message.from_user.id)
    username = message.from_user.username or "N/A"
    lang = detect_lang(message.from_user.language_code if message.from_user else None)

    logger.info(f"Help command received from user {user_id} (@{username})")

    try:
        db_session = await get_db_session()
        if db_session:
            try:
                user_repo = UserRepository(db_session)
                user = await user_repo.get_user_by_tg_id(user_id)
                if user and user.language_code:
                    lang = detect_lang(user.language_code)
            except Exception as e:
                logger.error(f"Failed to load user {user_id} for help lang: {e}")
            finally:
                await db_session.close()

        commands_list = t("start.commands_list", lang)
        tips = t("start.tips", lang)
        help_message = t("help.text", lang, commands=commands_list, tips=tips)
        await message.answer(help_message, parse_mode="HTML")
        logger.debug(f"Help message sent to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to handle help command for user {user_id}: {e}")
        try:
            await message.answer(t("help.error_processing", lang))
        except Exception:
            logger.error(f"Failed to send error message to user {user_id}")
