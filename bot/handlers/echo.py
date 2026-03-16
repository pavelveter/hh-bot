"""Handler for regular messages (non-command)"""

import html

from aiogram import Router
from aiogram.types import Message

from bot.handlers.search.run_search import run_search_and_reply
from bot.services import user_service
from bot.services.hh_service import hh_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.text import suggest_command

logger = get_logger(__name__)

router = Router()

KNOWN_COMMANDS = {
    "/start",
    "/help",
    "/profile",
    "/preferences",
    "/search",
    "/resume",
}


def _is_service_message(message: Message) -> bool:
    return any(
        getattr(message, attr, None) is not None
        for attr in (
            "forum_topic_created",
            "forum_topic_edited",
            "forum_topic_closed",
            "forum_topic_reopened",
            "general_forum_topic_hidden",
            "general_forum_topic_unhidden",
            "write_access_allowed",
        )
    )


def register_echo_handlers(router_instance: Router):
    """Register echo handlers"""
    try:
        router_instance.include_router(router)
        logger.info("Echo handlers registered successfully")
    except Exception as e:
        logger.error(f"Failed to register echo handlers: {e}")


@router.message()
async def echo_handler(message: Message):
    """Echo handler for any other messages with comprehensive logging and database integration"""
    if _is_service_message(message):
        logger.debug("Ignoring service message in echo handler")
        return

    user_id = str(message.from_user.id)
    username = message.from_user.username or "N/A"
    text = message.text or ""
    lang = detect_lang(message.from_user.language_code if message.from_user else None)
    user_obj = None
    user_db_id = None

    logger.info(
        f"Message received from user {user_id} (@{username}): '{text[:50]}{'...' if len(text) > 50 else ''}'"
    )

    try:
        # Resolve user and language preference up front
        user_obj, lang = await user_service.get_or_create_user_with_lang(
            tg_user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code,
        )
        user_db_id = user_obj.id if user_obj else None

        stripped = text.strip()
        if stripped.startswith("/"):
            nearest = suggest_command(stripped, lang)
            if nearest:
                await message.answer(
                    t("search.unknown_command_suggest", lang).format(
                        original=html.escape(stripped),
                        suggestion=nearest,
                    ),
                    parse_mode="HTML",
                )
                return
            await message.answer(t("search.unknown_command", lang))
            return

        # For non-command messages, treat them as search queries
        if stripped:
            # Check if HH service is available
            if not hh_service.session:
                await message.answer(t("search.service_unavailable", lang))
                return

            logger.debug(f"Treating message as search query for user {user_id}")
            await run_search_and_reply(message, user_obj, user_db_id, text, lang)
        else:
            logger.debug(f"Ignoring non-text or empty message from user {user_id}")

    except Exception as e:
        logger.error(f"Failed to handle message from user {user_id}: {e}")
        try:
            await message.answer(t("search.error_processing", lang))
        except Exception:
            logger.error(f"Failed to send error message to user {user_id}")
