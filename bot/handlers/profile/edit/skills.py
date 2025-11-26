import html

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.keyboards import skills_keyboard
from bot.handlers.profile.states import EditProfile
from bot.utils.i18n import detect_lang, t
from bot.utils.lang import resolve_lang
from bot.utils.profile_helpers import normalize_skills

router = Router()


async def send_skills_menu(message_obj: types.Message | types.CallbackQuery, tg_id: str, edit: bool = False):
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

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

    if isinstance(message_obj, types.CallbackQuery) and edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
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
    await call.message.answer(t("profile.edit_skills_prompt", lang))
    await state.set_state(EditProfile.skills)
    await call.answer()


@router.callback_query(F.data == "skills_back_profile")
async def cb_skills_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message)
    await call.answer()


@router.message(EditProfile.skills)
async def save_skills(message: types.Message, state: FSMContext):
    skills_input = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not skills_input:
        await message.answer(t("profile.edit_skills_empty", lang))
        return

    if skills_input.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, skills=None)
        await message.answer(t("profile.edit_skills_cleared", lang))
        await send_skills_menu(message, user_id)
        await state.clear()
        return

    skills = normalize_skills(skills_input)
    if not skills:
        await message.answer(t("profile.edit_skills_none", lang))
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, skills=skills)

    await message.answer(t("profile.edit_skills_updated", lang))
    await send_skills_menu(message, user_id)
    await state.clear()
