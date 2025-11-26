from __future__ import annotations

from aiogram import types

from bot.db import UserRepository
from bot.db.database import db_session
from bot.utils.i18n import detect_lang
from bot.utils.logging import get_logger

logger = get_logger(__name__)


async def get_or_create_user_lang(obj: types.CallbackQuery | types.Message):
    """Fetch user from DB (creating if needed) and detect language."""
    user_id = str(obj.from_user.id)
    lang = detect_lang(obj.from_user.language_code if obj.from_user else None)
    user = None
    async with db_session() as session:
        if session:
            try:
                user_repo = UserRepository(session)
                user = await user_repo.get_or_create_user(
                    tg_user_id=user_id,
                    username=obj.from_user.username,
                    first_name=obj.from_user.first_name,
                    last_name=obj.from_user.last_name,
                    language_code=obj.from_user.language_code,
                )
                lang = detect_lang(user.language_code)
            except Exception as e:
                logger.error(f"Failed to get/create user {user_id}: {e}")
    return user, lang
