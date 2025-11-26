from aiogram import F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.db.database import get_db_session
from bot.db.search_query_repository import SearchQueryRepository
from bot.db.user_repository import UserRepository
from bot.handlers.profile.states import EditPreferences
from bot.tasks.vacancy_delivery import send_vacancies_to_user
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.time import parse_time, utc_now

from . import router
from .common import cleanup_prompt_messages, prepare_preferences_view, refresh_preferences_message

logger = get_logger(__name__)


@router.message(Command("vacancy_schedule"))
async def cmd_vacancy_schedule(message: types.Message):
    tg_id = str(message.from_user.id)
    async with await get_db_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(
        user.language_code
        if user and user.language_code
        else (message.from_user.language_code if message.from_user else None)
    )

    if not user:
        await message.answer(t("profile.no_profile", lang))
        return

    prefs = user.preferences or {}
    schedule_time = prefs.get("vacancy_schedule_time")
    tz = prefs.get("timezone") or "Europe/Moscow"
    last_sent = prefs.get("vacancy_last_sent_at") or t("profile.not_set", lang)

    async with await get_db_session() as session:
        sq_repo = SearchQueryRepository(session)
        last_query = await sq_repo.get_latest_search_query_any(user.id)

    if not schedule_time:
        await message.answer(t("profile.preferences_schedule_info_empty", lang))
        return

    query_text = last_query.query_text if last_query and last_query.query_text else t("profile.not_set", lang)
    await message.answer(
        t("profile.preferences_schedule_info", lang).format(
            time=schedule_time,
            timezone=tz,
            query=query_text,
            last_sent=last_sent,
        )
    )


@router.message(Command("vacancy_schedule_test"))
async def cmd_vacancy_schedule_test(message: types.Message):
    tg_id = str(message.from_user.id)
    async with await get_db_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(
        user.language_code
        if user and user.language_code
        else (message.from_user.language_code if message.from_user else None)
    )
    if not user:
        await message.answer(t("profile.no_profile", lang))
        return

    now = utc_now()
    success = await send_vacancies_to_user(user, message.bot, now_utc=now, force=True, mark_sent=False)
    if success:
        await message.answer(t("profile.preferences_schedule_test_success", lang))
    else:
        await message.answer(t("profile.preferences_schedule_test_fail", lang))


@router.callback_query(F.data == "prefs_schedule_time")
async def cb_prefs_schedule_time(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    user, lang, _, _ = await prepare_preferences_view(tg_id, call.from_user.language_code if call.from_user else None)
    if not user:
        await call.message.answer(t("profile.no_profile", lang))
        await call.answer()
        return

    prompt = await call.message.answer(t("profile.preferences_schedule_prompt", lang))
    await state.set_state(EditPreferences.schedule_time)
    await state.update_data(
        prefs_message_id=call.message.message_id,
        prefs_chat_id=call.message.chat.id,
        prompt_message_id=prompt.message_id,
    )
    await call.answer()


@router.callback_query(F.data == "prefs_timezone")
async def cb_prefs_timezone(call: types.CallbackQuery, state: FSMContext):
    tg_id = str(call.from_user.id)
    user, lang, _, _ = await prepare_preferences_view(tg_id, call.from_user.language_code if call.from_user else None)
    if not user:
        await call.message.answer(t("profile.no_profile", lang))
        await call.answer()
        return

    prompt = await call.message.answer(t("profile.preferences_timezone_prompt", lang))
    await state.set_state(EditPreferences.timezone)
    await state.update_data(
        prefs_message_id=call.message.message_id,
        prefs_chat_id=call.message.chat.id,
        prompt_message_id=prompt.message_id,
    )
    await call.answer()


@router.message(EditPreferences.schedule_time)
async def save_schedule_time(message: types.Message, state: FSMContext):
    raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    _, lang, _, _ = await prepare_preferences_view(
        user_id, message.from_user.language_code if message.from_user else None
    )
    lowered = raw.lower()
    if lowered in {"clear", "none", "null", "удалить", "сбросить"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, vacancy_schedule_time=None)
        confirmation = await message.answer(t("profile.preferences_schedule_cleared", lang))
        await cleanup_prompt_messages(message, confirmation, state)
        await refresh_preferences_message(message, user_id, state)
        await state.clear()
        return

    parsed = parse_time(raw)
    if not parsed:
        await message.answer(t("profile.preferences_schedule_invalid", lang))
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, vacancy_schedule_time=parsed)

    confirmation = await message.answer(t("profile.preferences_schedule_saved", lang).format(time=parsed))
    await cleanup_prompt_messages(message, confirmation, state)
    await refresh_preferences_message(message, user_id, state)
    await state.clear()


@router.message(EditPreferences.timezone)
async def save_timezone(message: types.Message, state: FSMContext):
    raw = (message.text or "").strip()
    user_id = str(message.from_user.id)
    _, lang, _, _ = await prepare_preferences_view(
        user_id, message.from_user.language_code if message.from_user else None
    )
    lowered = raw.lower()
    if lowered in {"clear", "none", "null", "удалить", "сбросить"}:
        async with await get_db_session() as session:
            repo = UserRepository(session)
            await repo.update_preferences(user_id, timezone=None)
        confirmation = await message.answer(t("profile.preferences_timezone_cleared", lang))
        await cleanup_prompt_messages(message, confirmation, state)
        await refresh_preferences_message(message, user_id, state)
        await state.clear()
        return

    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(raw)
    except Exception:
        await message.answer(t("profile.preferences_timezone_invalid", lang))
        return

    async with await get_db_session() as session:
        repo = UserRepository(session)
        await repo.update_preferences(user_id, timezone=raw)

    confirmation = await message.answer(t("profile.preferences_timezone_saved", lang).format(timezone=raw))
    await cleanup_prompt_messages(message, confirmation, state)
    await refresh_preferences_message(message, user_id, state)
    await state.clear()
