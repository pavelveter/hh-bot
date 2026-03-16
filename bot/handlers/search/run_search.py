from bot.handlers.search.common import VACANCIES_PER_PAGE, build_search_keyboard
from bot.services import search_service, user_service
from bot.utils.i18n import t
from bot.utils.logging import get_logger
from bot.utils.profile_helpers import format_search_filters
from bot.utils.search import (
    cache_vacancies,
    format_search_page,
    get_query_thread_map,
    normalize_search_query_key,
    perform_search,
    store_search_results,
)

logger = get_logger(__name__)


async def run_search_and_reply(
    message, user_obj, user_db_id: int | None, query: str, lang: str
):
    """Shared search flow for /search and free-text messages."""
    prefs = user_obj.preferences if user_obj and user_obj.preferences else {}
    thread_id = getattr(message, "message_thread_id", None)
    search_filters = prefs.get("search_filters", {})
    area_id = user_obj.hh_area_id if user_obj else None

    results, response_time = await perform_search(
        query, per_page=100, area_id=area_id, filters=search_filters
    )

    if not results or not results.get("items"):
        if user_db_id:
            try:
                await search_service.create_search_query(
                    user_id=user_db_id,
                    query_text=query,
                    results_count=0,
                    response_time=response_time,
                )
            except Exception as e:
                logger.error(f"Failed to store search query for user {user_db_id}: {e}")

        if user_obj and thread_id:
            await _save_query_thread_binding(user_obj.tg_user_id, prefs, query, thread_id)

        filters_text = format_search_filters(search_filters, lang)
        city_text = (
            user_obj.city if user_obj and user_obj.city else t("profile.not_set", lang)
        )
        details = (
            f"\n\n<b>{t('profile.search_settings_title', lang).splitlines()[0]}</b>\n"
            f"{filters_text}\n"
            f"{t('location.current_city', lang, city=city_text)}"
        )

        await message.answer(
            t("search.no_results", lang).format(query=query) + details,
            parse_mode="HTML",
        )
        return

    vacancies = results["items"]
    total_found = results.get("found", len(vacancies))

    if user_db_id:
        await store_search_results(
            user_db_id, query, vacancies, response_time, per_page=100
        )
        cache_vacancies(user_db_id, query, vacancies, total_found)
        if user_obj and thread_id:
            await _save_query_thread_binding(user_obj.tg_user_id, prefs, query, thread_id)

    page = 0
    total_pages = (len(vacancies) + VACANCIES_PER_PAGE - 1) // VACANCIES_PER_PAGE
    response_text = format_search_page(
        query, vacancies, page, VACANCIES_PER_PAGE, total_found, lang
    )
    reply_markup = build_search_keyboard(
        query, page, total_pages, VACANCIES_PER_PAGE, len(vacancies)
    )

    await message.answer(
        response_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )
    logger.success(
        f"Search results sent to user {message.from_user.id} for query '{query}' "
        f"({len(vacancies)} vacancies, {total_pages} pages)"
    )


async def _save_query_thread_binding(
    tg_user_id: str, prefs: dict, query: str, thread_id: int
) -> None:
    query_threads = get_query_thread_map(prefs)
    query_key = normalize_search_query_key(query)
    if query_threads.get(query_key) == thread_id:
        return

    query_threads[query_key] = thread_id
    if not await user_service.update_preferences(tg_user_id, query_threads=query_threads):
        logger.warning(
            f"Failed to persist thread binding for user {tg_user_id}, query '{query}'"
        )
