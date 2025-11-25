from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.common import (
    CANCEL_COMMANDS,
    EditPreferences,
    EditProfile,
    EditSearchFilters,
    normalize_skills,
)
from bot.services.hh_service import hh_service
from bot.utils.i18n import t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger

logger = get_logger(__name__)
router = Router()


@router.message(
    StateFilter(EditProfile, EditSearchFilters, EditPreferences),
    F.text.casefold().in_(CANCEL_COMMANDS),
)
async def cancel_edit(message: types.Message, state: FSMContext):
    await state.clear()
    lang = await resolve_lang(
        str(message.from_user.id),
        message.from_user.language_code if message.from_user else None,
    )
    await message.answer(t("profile.edit_cancelled", lang))


# ---------------------
# EDIT CITY
# ---------------------


@router.callback_query(F.data == "edit_city")
async def cb_edit_city(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_city_prompt", lang))
    await state.set_state(EditProfile.city)
    await call.answer()


@router.message(EditProfile.city)
async def save_city(message: types.Message, state: FSMContext):
    city_input = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not city_input:
        await message.answer(t("profile.edit_city_empty", lang))
        return

    # Allow clearing city and area_id
    if city_input.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_user_city(user_id, None, None)
        await message.answer(t("profile.edit_city_cleared", lang))
        await state.clear()
        return

    # HH client is required to resolve area_id
    if not hh_service.session:
        await message.answer(t("profile.search_city_service_unavailable", lang))
        return

    await message.answer(t("profile.edit_city_lookup", lang).format(city=city_input))
    area_id = await hh_service.find_area_by_name(city_input)

    if not area_id:
        await message.answer(t("profile.edit_city_not_found", lang).format(city=city_input))
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_user_city(user_id, city_input, area_id)

    await message.answer(t("profile.edit_city_updated", lang).format(city=city_input))
    await state.clear()


# ---------------------
# EDIT POSITION
# ---------------------


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

    if position.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, desired_position=None)
        await message.answer(t("profile.edit_position_cleared", lang))
        await state.clear()
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, desired_position=position)

    await message.answer(t("profile.edit_position_updated", lang))
    await state.clear()


# ---------------------
# EDIT NAME
# ---------------------


@router.callback_query(F.data == "edit_name")
async def cb_edit_name(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_name_prompt", lang), parse_mode="HTML")
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

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_user_name(user_id, first_name=first, last_name=last)

    await message.answer(t("profile.edit_name_updated", lang))
    await state.clear()


# ---------------------
# EDIT SKILLS
# ---------------------


@router.callback_query(F.data == "edit_skills")
async def cb_edit_skills(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_skills_prompt", lang))
    await state.set_state(EditProfile.skills)
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
    await state.clear()


# ---------------------
# EDIT RESUME
# ---------------------


@router.callback_query(F.data == "edit_resume")
async def cb_edit_resume(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_resume_prompt", lang))
    await state.set_state(EditProfile.resume)
    await call.answer()


@router.message(EditProfile.resume)
async def save_resume(message: types.Message, state: FSMContext):
    resume_text = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not resume_text:
        await message.answer(t("profile.edit_resume_empty", lang))
        return

    if resume_text.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, resume=None)
        await message.answer(t("profile.edit_resume_cleared", lang))
        await state.clear()
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, resume=resume_text)

    await message.answer(t("profile.edit_resume_updated", lang))
    await state.clear()


# ---------------------
# EDIT LLM SETTINGS
# ---------------------


@router.callback_query(F.data == "edit_llm")
async def cb_edit_llm(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.edit_llm_prompt", lang), parse_mode="HTML")
    await state.set_state(EditProfile.llm)
    await call.answer()


@router.message(EditProfile.llm)
async def save_llm(message: types.Message, state: FSMContext):
    llm_raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not llm_raw:
        await message.answer(t("profile.edit_llm_empty", lang))
        return

    if llm_raw.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, llm_settings=None)
        await message.answer(t("profile.edit_llm_cleared", lang))
        await state.clear()
        return

    try:
        model, url, key = (s.strip() for s in llm_raw.split(";"))
    except ValueError:
        await message.answer(t("profile.edit_llm_bad_format", lang), parse_mode="HTML")
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, llm_settings={"model": model, "base_url": url, "api_key": key})

    # Best effort to remove sensitive message with API key
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete message with LLM settings for user {user_id}: {e}")

    await message.answer(t("profile.edit_llm_updated", lang))
    await state.clear()
