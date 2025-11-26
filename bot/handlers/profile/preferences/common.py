from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.keyboards import preferences_keyboard
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)


async def prepare_preferences_view(tg_id: str, fallback_lang: str | None = None):
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(user.language_code if user and user.language_code else fallback_lang)

    if not user:
        return None, lang, None, None

    prefs = user.preferences or {}
    lang_name = t(f"profile.languages.{lang}", lang)
    schedule_time = prefs.get("vacancy_schedule_time") or t("profile.not_set", lang)
    timezone = prefs.get("timezone") or "Europe/Moscow"
    text = t("profile.preferences_view", lang).format(language=lang_name, vacancy_time=schedule_time, timezone=timezone)
    markup = preferences_keyboard(False, lang)
    return user, lang, text, markup


async def cleanup_prompt_messages(message: types.Message, confirmation: types.Message, state: FSMContext):
    data = await state.get_data()
    prompt_id = data.get("prompt_message_id")
    to_delete = [prompt_id, message.message_id, confirmation.message_id]
    for msg_id in to_delete:
        if not msg_id:
            continue
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
        except Exception as e:
            logger.debug(f"Failed to delete schedule message {msg_id}: {e}")


async def refresh_preferences_message(message: types.Message, tg_id: str, state: FSMContext):
    data = await state.get_data()
    prefs_message_id = data.get("prefs_message_id")
    prefs_chat_id = data.get("prefs_chat_id")
    if not prefs_message_id or not prefs_chat_id:
        return

    user, lang, text, markup = await prepare_preferences_view(
        tg_id, message.from_user.language_code if message.from_user else None
    )
    if not user or not text or not markup:
        return

    try:
        await message.bot.edit_message_text(
            chat_id=prefs_chat_id,
            message_id=prefs_message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.debug(f"Failed to refresh preferences message for user {tg_id}: {e}")
