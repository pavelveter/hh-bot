from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.handlers.search.common import build_search_keyboard
from bot.services import search_service, user_service
from bot.services.hh_service import hh_service
from bot.utils.i18n import detect_lang
from bot.utils.logging import get_logger
from bot.utils.search import (
    cache_vacancies,
    format_search_page,
    get_query_thread_map,
    get_sent_vacancy_ids_by_query,
    normalize_search_query_key,
    perform_search,
    store_search_results,
)

logger = get_logger(__name__)

# Temporary default timezone until user timezones are added to preferences
DEFAULT_TZ = ZoneInfo("Europe/Moscow")
MAX_SENT_IDS = 200
MAX_VACANCIES_PER_USER = 20
DAILY_PER_PAGE = 5
MAX_TRACKED_QUERIES = 50


def _already_sent_today(prefs: dict, now_local: datetime, schedule_time: str) -> bool:
    last_sent_raw = prefs.get("vacancy_last_sent_at")
    if not last_sent_raw:
        return False
    try:
        last_dt = datetime.fromisoformat(last_sent_raw)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)
        last_local = last_dt.astimezone(now_local.tzinfo)
        # If schedule time changed for today, allow sending again
        if last_local.strftime("%Y-%m-%d") == now_local.strftime("%Y-%m-%d"):
            if last_local.strftime("%H:%M") != schedule_time:
                return False
            return True
        return False
    except Exception:
        return False


def _get_timezone(prefs: dict) -> ZoneInfo:
    tz_name = prefs.get("timezone")
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            logger.debug(f"Invalid timezone '{tz_name}', falling back to default")
    return DEFAULT_TZ


async def run_daily_vacancies(bot: Bot):
    """Send daily vacancies to users with a schedule time set."""
    if not hh_service.session:
        logger.warning("HH service not initialized; skipping daily vacancies job")
        return

    now_utc = datetime.now(UTC)
    users = await user_service.get_users_with_schedule()

    processed = 0
    for user in users:
        try:
            sent = await send_vacancies_to_user(user, bot, now_utc)
            if sent:
                processed += 1
        except Exception as e:
            logger.error(f"Failed to process user {user.tg_user_id} in scheduler: {e}")

    if processed:
        logger.debug(f"Daily vacancies job finished, sent to {processed} user(s)")


async def send_vacancies_to_user(
    user, bot: Bot, now_utc: datetime, force: bool = False, mark_sent: bool = True
):
    prefs = user.preferences or {}
    user_tz = _get_timezone(prefs)
    now_local = now_utc.astimezone(user_tz)
    current_time = now_local.strftime("%H:%M")

    schedule_time = prefs.get("vacancy_schedule_time")
    if not schedule_time:
        return False

    if not force and schedule_time != current_time:
        return False

    if not force and _already_sent_today(prefs, now_local, schedule_time):
        return False

    lang = detect_lang(user.language_code)
    query_records = await search_service.get_recent_distinct_search_queries(
        user.id, limit=MAX_TRACKED_QUERIES
    )
    if not query_records:
        logger.info(f"Skip user {user.tg_user_id}: no saved search queries")
        return False

    query_threads = get_query_thread_map(prefs)
    sent_ids_by_query = get_sent_vacancy_ids_by_query(prefs)
    filters = prefs.get("search_filters", {})
    area_id = user.hh_area_id
    any_sent = False
    updated_sent_ids_by_query = dict(sent_ids_by_query)

    for query_record in query_records:
        query_text = (query_record.query_text or "").strip()
        if not query_text:
            continue

        query_key = normalize_search_query_key(query_text)
        sent_ids = updated_sent_ids_by_query.get(query_key, [])
        sent_ids_set = set(sent_ids)

        try:
            results, response_time = await perform_search(
                query_text,
                per_page=MAX_VACANCIES_PER_USER,
                max_pages=1,
                search_in_name_only=True,
                area_id=area_id,
                filters=filters,
            )
        except Exception as e:
            logger.error(
                f"Search failed for user {user.tg_user_id}, query '{query_text}': {e}"
            )
            continue

        if not results or not results.get("items"):
            logger.info(
                f"No vacancies found for user {user.tg_user_id}, query '{query_text}' at {current_time}"
            )
            continue

        vacancies_all = results.get("items", [])
        vacancies_filtered = [
            vac for vac in vacancies_all if force or vac.get("id") not in sent_ids_set
        ]
        if not vacancies_filtered:
            logger.info(
                f"All vacancies already sent to user {user.tg_user_id} for query '{query_text}', skipping"
            )
            continue

        vacancies = vacancies_filtered[:MAX_VACANCIES_PER_USER]
        total_found = len(vacancies)
        per_page = DAILY_PER_PAGE

        await store_search_results(
            user.id, query_text, vacancies, response_time, per_page=per_page
        )
        cache_vacancies(user.id, query_text, vacancies, total_found)

        page = 0
        total_pages = (len(vacancies) + per_page - 1) // per_page
        text = format_search_page(
            query_text, vacancies, page, per_page, total_found, lang
        )
        reply_markup = build_search_keyboard(
            query_text, page, total_pages, per_page, len(vacancies)
        )

        send_kwargs = {
            "chat_id": user.tg_user_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": reply_markup,
        }
        thread_id = query_threads.get(query_key)
        if thread_id:
            send_kwargs["message_thread_id"] = thread_id

        try:
            await bot.send_message(**send_kwargs)
        except Exception as e:
            logger.error(
                f"Failed to send vacancies to user {user.tg_user_id} for query '{query_text}': {e}"
            )
            continue

        any_sent = True
        if not mark_sent:
            continue

        new_ids = [str(vac.get("id")) for vac in vacancies if vac.get("id")]
        updated_sent_ids_by_query[query_key] = (sent_ids + new_ids)[-MAX_SENT_IDS:]

    if not any_sent:
        return False

    if mark_sent:
        await user_service.update_preferences(
            user.tg_user_id,
            vacancy_last_sent_at=now_utc.isoformat(),
            sent_vacancy_ids_by_query=updated_sent_ids_by_query,
        )

    return True
