from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.handlers.profile.states import (
    CANCEL_COMMANDS,
    EditPreferences,
    EditProfile,
    EditSearchFilters,
)
from bot.handlers.profile.view import prepare_profile_view
from bot.utils.i18n import t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)


@router.message(
    StateFilter(EditProfile, EditSearchFilters, EditPreferences),
    F.text.casefold().in_(CANCEL_COMMANDS),
)
async def cancel_edit(message: types.Message, state: FSMContext):
    state_name = await state.get_state()
    state_data = await state.get_data()
    await state.clear()
    lang = await resolve_lang(
        str(message.from_user.id),
        message.from_user.language_code if message.from_user else None,
    )
    await _cleanup_prompt_message(message, state_data)
    await _safe_delete(message)

    if state_name == EditProfile.contacts.state:
        await _refresh_profile_view(message, str(message.from_user.id), state_data)
        return

    await message.answer(t("profile.edit_cancelled", lang))


async def _safe_delete(message: types.Message | None):
    if not message:
        return
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete message during cancel flow: {e}")


async def _cleanup_prompt_message(message: types.Message, state_data: dict):
    prompt_chat_id = (
        state_data.get("contacts_prompt_chat_id")
        or state_data.get("skills_prompt_chat_id")
        or state_data.get("resume_prompt_chat_id")
        or state_data.get("name_prompt_chat_id")
    )
    prompt_message_id = (
        state_data.get("contacts_prompt_message_id")
        or state_data.get("skills_prompt_message_id")
        or state_data.get("resume_prompt_message_id")
        or state_data.get("name_prompt_message_id")
    )
    if not prompt_message_id:
        return
    try:
        await message.bot.delete_message(
            chat_id=prompt_chat_id or message.chat.id,
            message_id=prompt_message_id,
        )
    except Exception as e:
        logger.debug(f"Failed to delete prompt message during cancel flow: {e}")


async def _refresh_profile_view(message: types.Message, tg_id: str, state_data: dict):
    menu_chat_id = state_data.get("contacts_menu_chat_id")
    menu_message_id = state_data.get("contacts_menu_message_id")
    if not menu_message_id:
        return
    try:
        user, lang, text, markup = await prepare_profile_view(tg_id, message)
        if not user or not text:
            return
        await message.bot.edit_message_text(
            chat_id=menu_chat_id or message.chat.id,
            message_id=menu_message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.debug(f"Failed to refresh profile view after cancel: {e}")
