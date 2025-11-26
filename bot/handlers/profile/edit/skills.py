import html

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from bot.handlers.profile.keyboards import skills_keyboard
from bot.handlers.profile.states import EditProfile
from bot.utils.i18n import detect_lang, t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger
from bot.utils.profile_edit import is_clear_command, load_user, update_user_prefs
from bot.utils.profile_helpers import normalize_skills

logger = get_logger(__name__)
router = Router()


async def send_skills_menu(
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

    if not user:
        await target.answer(t("profile.no_profile", lang))
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()
        return

    prefs = user.preferences or {}
    skills_list = prefs.get("skills") or []
    markup = skills_keyboard(lang)

    if not skills_list:
        text = t("profile.skills_menu_empty", lang)
    else:
        skills_text = ", ".join(html.escape(skill) for skill in skills_list)
        text = t("profile.skills_menu", lang, count=len(skills_list), skills=f"<code>{skills_text}</code>")

    bot = getattr(message_obj, "bot", None)

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
            logger.debug(f"Failed to edit skills menu by id: {e}")
        except Exception as e:
            logger.debug(f"Failed to edit skills menu by id: {e}")

    if isinstance(message_obj, types.CallbackQuery) and edit:
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                await message_obj.answer()
                return
            logger.debug(f"Failed to edit skills menu message: {e}")
            await target.answer(text, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.debug(f"Failed to edit skills menu message: {e}")
            await target.answer(text, parse_mode="HTML", reply_markup=markup)
        finally:
            await message_obj.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()


@router.callback_query(F.data == "skills_menu")
async def cb_skills_menu(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_skills_menu(call, str(call.from_user.id), edit=True)


@router.callback_query(F.data == "edit_skills")
async def cb_edit_skills(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    prompt = await call.message.answer(t("profile.edit_skills_prompt", lang))
    await state.update_data(
        skills_menu_chat_id=call.message.chat.id,
        skills_prompt_chat_id=call.message.chat.id,
        skills_prompt_message_id=prompt.message_id,
        skills_menu_message_id=call.message.message_id,
    )
    await state.set_state(EditProfile.skills)
    await call.answer()


@router.callback_query(F.data == "skills_back_profile")
async def cb_skills_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message, edit=True)
    await call.answer()


@router.message(EditProfile.skills)
async def save_skills(message: types.Message, state: FSMContext):
    skills_input = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    state_data = await state.get_data()
    prompt_chat_id = state_data.get("skills_prompt_chat_id")
    prompt_message_id = state_data.get("skills_prompt_message_id")
    menu_chat_id = state_data.get("skills_menu_chat_id")
    menu_message_id = state_data.get("skills_menu_message_id")

    async def _safe_delete(msg: types.Message | None):
        if not msg:
            return
        try:
            await msg.delete()
        except Exception as e:
            logger.debug(f"Failed to delete helper message during skills update: {e}")

    async def _delete_prompt():
        if prompt_message_id and (prompt_chat_id or menu_chat_id):
            try:
                await message.bot.delete_message(
                    chat_id=prompt_chat_id or menu_chat_id or message.chat.id, message_id=prompt_message_id
                )
            except Exception as e:
                logger.debug(f"Failed to delete skills prompt message: {e}")

    if not skills_input:
        await message.answer(t("profile.edit_skills_empty", lang))
        return

    if is_clear_command(skills_input):
        await update_user_prefs(user_id, skills=None)
        confirm = await message.answer(t("profile.edit_skills_cleared", lang))
        await send_skills_menu(
            message,
            user_id,
            edit=True,
            chat_id=menu_chat_id or message.chat.id,
            message_id=menu_message_id,
        )
        await _safe_delete(message)
        await _delete_prompt()
        await _safe_delete(confirm)
        await state.clear()
        return

    skills = normalize_skills(skills_input)
    if not skills:
        await message.answer(t("profile.edit_skills_none", lang))
        return

    await update_user_prefs(user_id, skills=skills)

    confirm = await message.answer(t("profile.edit_skills_updated", lang))
    await send_skills_menu(
        message,
        user_id,
        edit=True,
        chat_id=menu_chat_id or message.chat.id,
        message_id=menu_message_id,
    )

    await _safe_delete(message)
    await _delete_prompt()
    await _safe_delete(confirm)
    await state.clear()
