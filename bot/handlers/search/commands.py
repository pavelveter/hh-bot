"""Handler for /search command"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import SearchQueryRepository, UserRepository
from bot.db.database import get_db_session
from bot.handlers.search.common import VACANCIES_PER_PAGE, build_search_keyboard
from bot.services.hh_service import hh_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.search import (
    cache_vacancies,
    format_search_page,
    get_vacancies_from_db,
    perform_search,
    store_search_results,
)

logger = get_logger(__name__)

router = Router()


@router.message(Command("search"))
async def search_handler(message: Message):
    """Handler for the /search command with comprehensive logging and database integration"""
    user_id = str(message.from_user.id)
    username = message.from_user.username or "N/A"
    lang = detect_lang(message.from_user.language_code if message.from_user else None)

    # Extract search query from message
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

    logger.info(f"Search command received from user {user_id} (@{username}) with query: '{query}'")

    try:
        # Get user from database to get user ID and preferences
        db_session = await get_db_session()
        user_db_id = None
        user_obj = None
        if db_session:
            try:
                user_repo = UserRepository(db_session)
                user_obj = await user_repo.get_or_create_user(
                    tg_user_id=user_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                    language_code=message.from_user.language_code,
                )
                user_db_id = user_obj.id
                lang = detect_lang(user_obj.language_code)
            except Exception as e:
                logger.error(f"Failed to get user {user_id} from database: {e}")
            finally:
                await db_session.close()

        # If no query provided, try to show the last search results
        if not query:
            if not user_db_id:
                await message.answer(t("search.no_profile", lang))
                return
            db_session = await get_db_session()
            last_query = None
            if db_session:
                try:
                    search_repo = SearchQueryRepository(db_session)
                    last_query = await search_repo.get_latest_search_query_any(user_db_id)
                except Exception as e:
                    logger.error(f"Failed to get last search query for user {user_id}: {e}")
                finally:
                    await db_session.close()

            if not last_query:
                await message.answer(t("search.no_previous", lang))
                return

            query = last_query.query_text
            vacancies, total_found = await get_vacancies_from_db(user_db_id, query)
            if not vacancies:
                await message.answer(t("search.no_saved_results", lang))
                return

            # Format first page from stored results
            page = 0
            total_pages = (len(vacancies) + VACANCIES_PER_PAGE - 1) // VACANCIES_PER_PAGE
            response_text = format_search_page(query, vacancies, page, VACANCIES_PER_PAGE, total_found, lang)
            reply_markup = build_search_keyboard(query, page, total_pages, VACANCIES_PER_PAGE, len(vacancies))

            await message.answer(
                response_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
            logger.info(f"Sent last search results to user {user_id} for query '{query}'")
            return

        # Check if HH service is available for new searches
        if not hh_service.session:
            logger.error(f"HH service not available for user {user_id}")
            await message.answer(t("search.service_unavailable", lang))
            return

        # Show loading message
        loading_msg = await message.answer(t("search.loading", lang))

        prefs = user_obj.preferences if user_obj and user_obj.preferences else {}
        search_filters = prefs.get("search_filters", {})
        area_id = user_obj.hh_area_id if user_obj else None
        user_city_info = (user_obj.city, user_obj.hh_area_id) if user_obj else None
        logger.debug(
            f"Performing search for query '{query}' for user {user_id} "
            f"(city: {user_city_info[0] if user_city_info else 'any'}, area_id: {area_id})"
        )
        results, response_time = await perform_search(query, per_page=100, area_id=area_id, filters=search_filters)

        if not results or not results.get("items"):
            await loading_msg.delete()
            logger.info(f"No vacancies found for query '{query}' for user {user_id}")

            # Store search query even if no results found
            if user_db_id:
                db_session = await get_db_session()
                if db_session:
                    try:
                        search_repo = SearchQueryRepository(db_session)
                        await search_repo.create_search_query(
                            user_id=user_db_id,
                            query_text=query,
                            results_count=0,
                            response_time=response_time,
                        )
                        logger.debug(f"Stored search query with no results for user {user_db_id}")
                    except Exception as e:
                        logger.error(f"Failed to store search query for user {user_db_id}: {e}")
                    finally:
                        await db_session.close()

            await message.answer(t("search.no_results", lang).format(query=query))
            return

        # Get all vacancies
        vacancies = results["items"]
        total_found = results.get("found", len(vacancies))

        # Store all search results in database
        if user_db_id:
            await store_search_results(user_db_id, query, vacancies, response_time, per_page=100)
            # Cache the results for fast pagination
            cache_vacancies(user_db_id, query, vacancies, total_found)

        # Format first page
        page = 0
        total_pages = (len(vacancies) + VACANCIES_PER_PAGE - 1) // VACANCIES_PER_PAGE
        response_text = format_search_page(query, vacancies, page, VACANCIES_PER_PAGE, total_found, lang)

        # Create keyboard with vacancy detail buttons + pagination
        reply_markup = build_search_keyboard(query, page, total_pages, VACANCIES_PER_PAGE, len(vacancies))

        await loading_msg.delete()
        await message.answer(
            response_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
        logger.success(
            f"Search results sent to user {user_id} for query '{query}' ({len(vacancies)} vacancies, {total_pages} pages)"
        )

    except Exception as e:
        logger.error(f"Failed to handle search command for user {user_id}, query '{query}': {e}")
        try:
            await message.answer(t("search.error_processing", lang))
        except Exception:
            logger.error(f"Failed to send error message to user {user_id}")
