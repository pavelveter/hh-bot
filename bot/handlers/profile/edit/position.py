from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.handlers.profile.states import EditProfile
from bot.utils.i18n import t
from bot.utils.lang import resolve_lang
from bot.utils.profile_edit import is_clear_command, update_user_prefs

router = Router()


@router.callback_query(F.data == "edit_position")
async def cb_edit_position(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_position_prompt", lang))
    await state.set_state(EditProfile.position)
    await call.answer()


@router.message(EditProfile.position)
async def save_position(message: types.Message, state: FSMContext):
    position = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not position:
        await message.answer(t("profile.edit_position_empty", lang))
        return

    if is_clear_command(position):
        await update_user_prefs(user_id, desired_position=None)
        await message.answer(t("profile.edit_position_cleared", lang))
        await state.clear()
        return

    await update_user_prefs(user_id, desired_position=position)

    await message.answer(t("profile.edit_position_updated", lang))
    await state.clear()
