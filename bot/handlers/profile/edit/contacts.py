from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from bot.handlers.profile.states import EditProfile
from bot.handlers.profile.view import prepare_profile_view
from bot.utils.i18n import t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger
from bot.utils.profile_edit import is_clear_command, update_user_prefs

logger = get_logger(__name__)
router = Router()


@router.callback_query(F.data == "edit_contacts")
async def cb_edit_contacts(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(
        str(call.from_user.id), call.from_user.language_code if call.from_user else None
    )
    prompt = await call.message.answer(t("profile.edit_contacts_prompt", lang))
    await state.update_data(
        contacts_prompt_chat_id=call.message.chat.id,
        contacts_prompt_message_id=prompt.message_id,
        contacts_menu_chat_id=call.message.chat.id,
        contacts_menu_message_id=call.message.message_id,
    )
    await state.set_state(EditProfile.contacts)
    await call.answer()


async def _safe_delete(message: types.Message | None):
    if not message:
        return
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete contacts helper message: {e}")


async def _delete_prompt(
    message: types.Message,
    prompt_chat_id: int | None,
    prompt_message_id: int | None,
    fallback_chat_id: int | None = None,
):
    if not prompt_message_id:
        return
    try:
        await message.bot.delete_message(
            chat_id=prompt_chat_id or fallback_chat_id or message.chat.id,
            message_id=prompt_message_id,
        )
    except Exception as e:
        logger.debug(f"Failed to delete contacts prompt message: {e}")


async def _refresh_profile_view(
    message: types.Message,
    tg_id: str,
    menu_chat_id: int | None,
    menu_message_id: int | None,
):
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
    except TelegramBadRequest as e:
        logger.debug(f"Failed to refresh profile view after contacts update: {e}")
    except Exception as e:
        logger.debug(f"Failed to refresh profile view after contacts update: {e}")


@router.message(EditProfile.contacts)
async def save_contacts(message: types.Message, state: FSMContext):
    contacts = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(
        user_id, message.from_user.language_code if message.from_user else None
    )

    state_data = await state.get_data()
    prompt_chat_id = state_data.get("contacts_prompt_chat_id")
    prompt_message_id = state_data.get("contacts_prompt_message_id")
    menu_chat_id = state_data.get("contacts_menu_chat_id")
    menu_message_id = state_data.get("contacts_menu_message_id")

    if is_clear_command(contacts):
        await update_user_prefs(user_id, contacts=None)
        confirm = await message.answer(t("profile.edit_contacts_cleared", lang))
        await _refresh_profile_view(
            message, user_id, menu_chat_id=menu_chat_id, menu_message_id=menu_message_id
        )
        await _safe_delete(message)
        await _delete_prompt(message, prompt_chat_id, prompt_message_id, menu_chat_id)
        await _safe_delete(confirm)
        await state.clear()
        return

    if not contacts:
        await message.answer(t("profile.edit_contacts_empty", lang))
        return

    await update_user_prefs(user_id, contacts=contacts)
    confirm = await message.answer(t("profile.edit_contacts_updated", lang))
    await _refresh_profile_view(
        message, user_id, menu_chat_id=menu_chat_id, menu_message_id=menu_message_id
    )
    await _safe_delete(message)
    await _delete_prompt(message, prompt_chat_id, prompt_message_id, menu_chat_id)
    await _safe_delete(confirm)
    await state.clear()
