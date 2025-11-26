from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.handlers.profile.preferences.common import prepare_preferences_view
from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)

from . import router  # noqa: E402  # router is defined in __init__


async def send_preferences_view(message_obj: types.Message | types.CallbackQuery, tg_id: str, edit: bool = False):
    user, lang, text, markup = await prepare_preferences_view(
        tg_id,
        message_obj.from_user.language_code if message_obj.from_user else None,
    )
    if not user:
        target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
        await target.answer(t("profile.no_profile", lang))
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()
        return

    target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
    if isinstance(message_obj, types.CallbackQuery) and edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
        await message_obj.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()


@router.message(Command("preferences"))
async def cmd_preferences(message: types.Message):
    await send_preferences_view(message, str(message.from_user.id))


@router.callback_query(F.data == "prefs_menu")
async def cb_prefs_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_preferences_view(call, str(call.from_user.id), edit=True)


@router.callback_query(F.data == "prefs_back_profile")
async def cb_prefs_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message, edit=True)
    await call.answer()
