import html

from aiogram import Router, types
from aiogram.filters import Command

from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.common import format_search_filters, hide_key, profile_keyboard, short
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)
router = Router()


async def send_profile_view(tg_id: str, message_obj: types.Message):
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(
        user.language_code if user else (message_obj.from_user.language_code if message_obj.from_user else None)
    )

    if not user:
        await message_obj.answer(t("profile.no_profile", lang))
        return

    prefs = user.preferences or {}
    llm = prefs.get("llm_settings", {})
    search_filters = prefs.get("search_filters", {})

    city = html.escape(user.city) if user.city else "not set"
    desired_position = html.escape(prefs.get("desired_position", "")) if prefs.get("desired_position") else "not set"
    skills_list = prefs.get("skills", [])
    skills = ", ".join(html.escape(s) for s in skills_list) if skills_list else "not set"
    llm_model = html.escape(llm.get("model")) if llm.get("model") else "not set"
    llm_url = html.escape(llm.get("base_url")) if llm.get("base_url") else "not set"
    llm_key = hide_key(llm.get("api_key"))
    username = f"@{html.escape(user.username)}" if user.username else "not set"
    name = f"{html.escape(user.first_name or '')} {html.escape(user.last_name or '')}".strip()
    search_filters_text = format_search_filters(search_filters, lang)

    text = t(
        "profile.view",
        lang,
        tg_id=user.tg_user_id,
        username=username,
        name=name or "not set",
        city=city,
        desired_position=desired_position,
        skills=skills,
        resume=short(prefs.get("resume"), lang),
        search_filters=search_filters_text,
        llm_model=llm_model,
        llm_url=llm_url,
        llm_key=llm_key,
    )

    await message_obj.answer(text, parse_mode="HTML", reply_markup=profile_keyboard(lang))


@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    await send_profile_view(str(message.from_user.id), message)


@router.message(Command("resume"))
async def cmd_resume(message: types.Message):
    tg_id = str(message.from_user.id)

    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)

    lang = detect_lang(user.language_code if user else (message.from_user.language_code if message.from_user else None))

    if not user:
        await message.answer(t("profile.no_profile", lang))
        return

    prefs = user.preferences or {}
    resume = prefs.get("resume")

    if not resume:
        await message.answer(t("profile.resume_missing", lang))
        return

    await message.answer(
        f"{t('profile.resume_header', lang)}\n\n" + html.escape(resume),
        parse_mode="HTML",
    )
