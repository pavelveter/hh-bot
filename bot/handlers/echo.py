"""Handler for regular messages (non-command)"""

from aiogram import Router
from aiogram.types import Message

from bot.db import SearchQueryRepository, UserRepository
from bot.db.database import get_db_session
from bot.services.hh_service import hh_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.search import (
    format_search_response,
    perform_search,
    store_search_results,
)

logger = get_logger(__name__)

router = Router()


def register_echo_handlers(router_instance: Router):
    """Register echo handlers"""
    try:
        router_instance.include_router(router)
        logger.info("Echo handlers registered successfully")
    except Exception as e:
        logger.error(f"Failed to register echo handlers: {e}")


@router.message()
async def echo_handler(message: Message):
    """Echo handler for any other messages with comprehensive logging and database integration"""
    user_id = str(message.from_user.id)
    username = message.from_user.username or "N/A"
    text = message.text or "[non-text message]"
    lang = detect_lang(message.from_user.language_code if message.from_user else None)

    logger.info(f"Message received from user {user_id} (@{username}): '{text[:50]}{'...' if len(text) > 50 else ''}'")

    try:
        # For non-command messages, treat them as search queries
        if text.strip() and not text.startswith("/"):
            # Check if HH service is available
            if not hh_service.session:
                await message.answer(t("search.service_unavailable", lang))
                return

            # Get user from database to get user ID
            db_session = await get_db_session()
            user_db_id = None
            user_obj = None
            if db_session:
                try:
                    user_repo = UserRepository(db_session)
                    user = await user_repo.get_or_create_user(
                        tg_user_id=user_id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name,
                        language_code=message.from_user.language_code,
                    )
                    user_db_id = user.id
                    user_obj = user
                    lang = detect_lang(user.language_code)
                except Exception as e:
                    logger.error(f"Failed to get user {user_id} from database: {e}")
                finally:
                    await db_session.close()

            logger.debug(f"Treating message as search query for user {user_id}")
            prefs = user_obj.preferences if user_obj and user_obj.preferences else {}
            search_filters = prefs.get("search_filters", {})
            area_id = user_obj.hh_area_id if user_obj else None

            results, response_time = await perform_search(text, per_page=3, area_id=area_id, filters=search_filters)

            if not results or not results.get("items"):
                logger.info(f"No vacancies found for query '{text}' from user {user_id}")

                # Store search query even if no results found
                if user_db_id:
                    db_session = await get_db_session()
                    if db_session:
                        try:
                            search_repo = SearchQueryRepository(db_session)
                            await search_repo.create_search_query(
                                user_id=user_db_id,
                                query_text=text,
                                results_count=0,
                                response_time=response_time,
                            )
                            logger.debug(f"Stored search query with no results for user {user_db_id}")
                        except Exception as e:
                            logger.error(f"Failed to store search query for user {user_db_id}: {e}")
                        finally:
                            await db_session.close()

                await message.answer(t("search.no_results", lang).format(query=text))
                return

            # Format and send results
            vacancies = results["items"]
            response = await format_search_response(text, results, lang, max_results=3)

            # Store search query and results in database
            if user_db_id:
                await store_search_results(user_db_id, text, vacancies[:3], response_time, per_page=3)

            await message.answer(response, parse_mode="HTML", disable_web_page_preview=True)
            logger.success(f"Search results sent to user {user_id} for query '{text}'")
        else:
            help_message = t("search.echo_help", lang)
            await message.answer(help_message)
            logger.debug(f"Echo message sent to user {user_id}")

    except Exception as e:
        logger.error(f"Failed to handle message from user {user_id}: {e}")
        try:
            await message.answer(t("search.error_processing", lang))
        except Exception:
            logger.error(f"Failed to send error message to user {user_id}")
