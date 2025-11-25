from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.common import (
    EditSearchFilters,
    employment_keyboard,
    experience_keyboard,
    format_search_filters,
    search_settings_keyboard,
)
from bot.handlers.profile.view import send_profile_view
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)
router = Router()


async def get_search_filters(tg_id: str) -> dict:
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)
        prefs = user.preferences if user and user.preferences else {}
        return prefs.get("search_filters", {})


async def send_search_settings(message_obj: types.Message | types.CallbackQuery, tg_id: str, edit: bool = False):
    filters = await get_search_filters(tg_id)
    lang = detect_lang(
        (
            message_obj.from_user.language_code
            if isinstance(message_obj, types.Message) and message_obj.from_user
            else None
        )
        if not isinstance(message_obj, types.CallbackQuery)
        else (message_obj.from_user.language_code if message_obj.from_user else None)
    )
    text = t("profile.search_settings_title", lang).format(filters=format_search_filters(filters, lang))
    markup = search_settings_keyboard(filters, lang)

    if isinstance(message_obj, types.CallbackQuery):
        try:
            if edit:
                await message_obj.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            else:
                await message_obj.message.answer(text, parse_mode="HTML", reply_markup=markup)
        finally:
            await message_obj.answer()
    else:
        await message_obj.answer(text, parse_mode="HTML", reply_markup=markup)


@router.message(Command("search_settings"))
async def cmd_search_settings(message: types.Message):
    await send_search_settings(message, str(message.from_user.id))


@router.callback_query(F.data == "search_settings")
async def cb_search_settings(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_search_settings(call, str(call.from_user.id), edit=True)


@router.callback_query(F.data == "search_back_profile")
async def cb_search_back_profile(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = str(call.from_user.id)
    await send_profile_view(tg_id, call.message)
    await call.answer()


@router.callback_query(F.data == "search_set_salary")
async def cb_search_set_salary(call: types.CallbackQuery, state: FSMContext):
    lang = detect_lang(call.from_user.language_code if call.from_user else None)
    await call.message.answer(t("profile.search_set_salary_prompt", lang))
    await state.set_state(EditSearchFilters.min_salary)
    await call.answer()


@router.message(EditSearchFilters.min_salary)
async def save_min_salary(message: types.Message, state: FSMContext):
    raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = detect_lang(message.from_user.language_code if message.from_user else None)

    if raw.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        value = None
    else:
        if not raw.isdigit():
            await message.answer(t("profile.search_salary_invalid", lang))
            return
        value = int(raw)

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_search_filters(user_id, min_salary=value)

    await send_search_settings(message, user_id)
    await state.clear()


@router.callback_query(F.data == "search_toggle_remote")
async def cb_toggle_remote(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    filters = await get_search_filters(tg_id)
    new_value = not bool(filters.get("remote_only"))

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_search_filters(tg_id, remote_only=new_value)

    await send_search_settings(call, tg_id, edit=True)


@router.callback_query(F.data.startswith("search_freshness:"))
async def cb_set_freshness(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    try:
        value = call.data.split(":")[1]
        days = None if value == "clear" else int(value)
    except Exception:
        days = None

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_search_filters(tg_id, freshness_days=days)

    await send_search_settings(call, tg_id, edit=True)


@router.callback_query(F.data == "search_employment_menu")
async def cb_employment_menu(call: types.CallbackQuery, state: FSMContext):
    filters = await get_search_filters(str(call.from_user.id))
    current = filters.get("employment")
    await call.message.edit_text(
        t("profile.search_employment_title", detect_lang(call.from_user.language_code if call.from_user else None)),
        parse_mode="HTML",
        reply_markup=employment_keyboard(
            current, detect_lang(call.from_user.language_code if call.from_user else None)
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("search_set_employment:"))
async def cb_set_employment(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    value = call.data.split(":")[1]
    employment_value = None if value == "clear" else value

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_search_filters(tg_id, employment=employment_value)

    await send_search_settings(call, tg_id, edit=True)


@router.callback_query(F.data == "search_experience_menu")
async def cb_experience_menu(call: types.CallbackQuery, state: FSMContext):
    filters = await get_search_filters(str(call.from_user.id))
    current = filters.get("experience")
    await call.message.edit_text(
        t("profile.search_experience_title", detect_lang(call.from_user.language_code if call.from_user else None)),
        parse_mode="HTML",
        reply_markup=experience_keyboard(
            current, detect_lang(call.from_user.language_code if call.from_user else None)
        ),
    )
    await call.answer()


@router.callback_query(F.data.startswith("search_set_experience:"))
async def cb_set_experience(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    value = call.data.split(":")[1]
    experience_value = None if value == "clear" else value

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_search_filters(tg_id, experience=experience_value)

    await send_search_settings(call, tg_id, edit=True)


@router.callback_query(F.data == "search_clear_filters")
async def cb_clear_filters(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_search_filters(
            tg_id,
            min_salary=None,
            remote_only=None,
            freshness_days=None,
            employment=None,
            experience=None,
        )
    await send_search_settings(call, tg_id, edit=True)
