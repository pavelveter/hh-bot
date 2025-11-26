from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.db.database import db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.states import EditProfile
from bot.utils.i18n import t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger

logger = get_logger(__name__)
router = Router()


@router.callback_query(F.data == "edit_name")
async def cb_edit_name(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    prompt = await call.message.answer(t("profile.edit_name_prompt", lang), parse_mode="HTML")
    await state.update_data(
        name_prompt_chat_id=call.message.chat.id,
        name_prompt_message_id=prompt.message_id,
        name_menu_message_id=call.message.message_id,
    )
    await state.set_state(EditProfile.name)
    await call.answer()


@router.message(EditProfile.name)
async def save_name(message: types.Message, state: FSMContext):
    name_raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if name_raw.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        first, last = None, None
    else:
        if not name_raw:
            await message.answer(t("profile.edit_name_empty", lang))
            return
        parts = name_raw.split(maxsplit=1)
        first = parts[0].strip()
        last = parts[1].strip() if len(parts) > 1 else None
        if not first:
            await message.answer(t("profile.edit_name_first_empty", lang))
            return

    async with db_session() as session:
        repo = UserRepository(session)
        await repo.update_user_name(user_id, first_name=first, last_name=last)

    state_data = await state.get_data()
    prompt_chat_id = state_data.get("name_prompt_chat_id")
    prompt_message_id = state_data.get("name_prompt_message_id")

    confirm_msg = await message.answer(t("profile.edit_name_updated", lang))

    async def _safe_delete(msg: types.Message | None):
        if not msg:
            return
        try:
            await msg.delete()
        except Exception as e:
            logger.debug(f"Failed to delete helper message during name update: {e}")

    await _safe_delete(message)

    if prompt_message_id and prompt_chat_id:
        try:
            await message.bot.delete_message(chat_id=prompt_chat_id, message_id=prompt_message_id)
        except Exception as e:
            logger.debug(f"Failed to delete name prompt message: {e}")

    await _safe_delete(confirm_msg)
    await state.clear()
