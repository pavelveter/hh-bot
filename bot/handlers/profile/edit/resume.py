import html

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from bot.handlers.profile.keyboards import resume_keyboard
from bot.handlers.profile.states import EditProfile
from bot.utils.i18n import detect_lang, t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger
from bot.utils.profile_edit import is_clear_command, load_user, update_user_prefs

logger = get_logger(__name__)
router = Router()


async def send_resume_menu(
    message_obj: types.Message | types.CallbackQuery,
    tg_id: str,
    edit: bool = False,
    chat_id: int | None = None,
    message_id: int | None = None,
):
    user = await load_user(tg_id)

    lang = detect_lang(
        user.language_code
        if user and user.language_code
        else (message_obj.from_user.language_code if message_obj.from_user else None)
    )
    target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
    bot = getattr(message_obj, "bot", None)

    if not user:
        await target.answer(t("profile.no_profile", lang))
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()
        return

    prefs = user.preferences or {}
    resume = prefs.get("resume")
    markup = resume_keyboard(lang)

    if resume:
        safe_resume = html.escape(resume)
        text = t("profile.resume_menu", lang, resume=f"<code>{safe_resume}</code>")
    else:
        text = t("profile.resume_menu_empty", lang)

    if message_id and bot and chat_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=markup,
            )
            if isinstance(message_obj, types.CallbackQuery):
                await message_obj.answer()
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                if isinstance(message_obj, types.CallbackQuery):
                    await message_obj.answer()
                return
            logger.debug(f"Failed to edit resume menu by id: {e}")
        except Exception as e:
            logger.debug(f"Failed to edit resume menu by id: {e}")

    if isinstance(message_obj, types.CallbackQuery) and edit:
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                await message_obj.answer()
                return
            logger.debug(f"Failed to edit resume menu message: {e}")
            await target.answer(text, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.debug(f"Failed to edit resume menu message: {e}")
            await target.answer(text, parse_mode="HTML", reply_markup=markup)
        finally:
            await message_obj.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()


@router.callback_query(F.data == "resume_menu")
async def cb_resume_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_resume_menu(call, str(call.from_user.id), edit=True)


@router.callback_query(F.data.in_({"resume_edit", "edit_resume"}))
async def cb_edit_resume(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    prompt = await call.message.answer(t("profile.edit_resume_prompt", lang))
    await state.update_data(
        resume_prompt_chat_id=call.message.chat.id,
        resume_prompt_message_id=prompt.message_id,
        resume_menu_message_id=call.message.message_id,
    )
    await state.set_state(EditProfile.resume)
    await call.answer()


@router.callback_query(F.data == "resume_back_profile")
async def cb_resume_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message, edit=True)
    await call.answer()


async def _safe_delete(message: types.Message | None, context_state: FSMContext | None = None):
    if not message:
        return
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to delete helper message during resume update: {e}")


async def _cleanup_messages(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    prompt_chat_id = state_data.get("resume_prompt_chat_id")
    prompt_message_id = state_data.get("resume_prompt_message_id")

    await _safe_delete(message, state)

    if prompt_message_id and prompt_chat_id:
        try:
            await message.bot.delete_message(chat_id=prompt_chat_id, message_id=prompt_message_id)
        except Exception as e:
            logger.debug(f"Failed to delete resume prompt message: {e}")


@router.message(EditProfile.resume)
async def save_resume(message: types.Message, state: FSMContext):
    resume_text = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not resume_text:
        await message.answer(t("profile.edit_resume_empty", lang))
        return

    if is_clear_command(resume_text):
        await update_user_prefs(user_id, resume=None)
        confirm = await message.answer(t("profile.edit_resume_cleared", lang))
        state_data = await state.get_data()
        await send_resume_menu(
            message,
            user_id,
            edit=True,
            chat_id=state_data.get("resume_menu_chat_id") or message.chat.id,
            message_id=state_data.get("resume_menu_message_id"),
        )
        await _cleanup_messages(message, state)
        await _safe_delete(confirm, state)
        await state.clear()
        return

    await update_user_prefs(user_id, resume=resume_text)

    confirm = await message.answer(t("profile.edit_resume_updated", lang))
    state_data = await state.get_data()
    await send_resume_menu(
        message,
        user_id,
        edit=True,
        chat_id=state_data.get("resume_menu_chat_id") or message.chat.id,
        message_id=state_data.get("resume_menu_message_id"),
    )
    await _cleanup_messages(message, state)
    await _safe_delete(confirm, state)
    await state.clear()
