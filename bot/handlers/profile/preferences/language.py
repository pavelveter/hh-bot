from aiogram import F, types

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)

from . import router  # noqa: E402
from .view import send_preferences_view  # noqa: E402


@router.callback_query(F.data == "prefs_lang_menu")
async def cb_prefs_lang_menu(call: types.CallbackQuery, state):
    lang = detect_lang(call.from_user.language_code if call.from_user else None)
    buttons = [
        [types.InlineKeyboardButton(text=t("profile.languages.en", lang), callback_data="prefs_set_lang:en")],
        [types.InlineKeyboardButton(text=t("profile.languages.ru", lang), callback_data="prefs_set_lang:ru")],
        [types.InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="prefs_menu")],
    ]
    await call.message.answer(
        t("profile.preferences_lang_prompt", lang), reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.clear()
    await call.answer()


@router.callback_query(F.data.startswith("prefs_set_lang:"))
async def cb_prefs_set_lang(call: types.CallbackQuery, state):
    _, _, code = call.data.partition(":")
    if code not in {"en", "ru"}:
        lang = detect_lang(call.from_user.language_code if call.from_user else None)
        await call.message.answer(t("profile.preferences_lang_invalid", lang))
        await call.answer()
        return

    target_lang = detect_lang(code)
    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_language_code(str(call.from_user.id), target_lang)

    lang_name = t(f"profile.languages.{target_lang}", target_lang)
    await call.message.answer(t("profile.preferences_lang_saved", target_lang).format(language=lang_name))
    await call.answer()
    await send_preferences_view(call, str(call.from_user.id), edit=True)
