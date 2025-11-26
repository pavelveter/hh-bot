from aiogram import Router
from aiogram.types import CallbackQuery

from bot.handlers.search.common import VACANCIES_PER_PAGE, build_search_keyboard, safe_answer
from bot.handlers.search.helpers import get_or_create_user_lang
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.search import format_search_page, get_vacancies_from_db

logger = get_logger(__name__)

router = Router()


@router.callback_query(lambda c: c.data.startswith("search_page:"))
async def pagination_handler(callback: CallbackQuery):
    """Handler for pagination callbacks"""
    # Handle non-functional buttons (like ellipsis)
    if callback.data == "noop":
        await safe_answer(callback)
        return

    user_id = str(callback.from_user.id)
    username = callback.from_user.username or "N/A"
    lang = detect_lang(callback.from_user.language_code if callback.from_user else None)

    try:
        # Parse callback data: search_page:query:page
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await safe_answer(callback, text=t("search.pagination.invalid_request", lang), show_alert=True)
            return

        query = parts[1]
        page = int(parts[2])

        logger.info(f"Pagination request from user {user_id} (@{username}): query '{query}', page {page}")

        user_obj, lang = await get_or_create_user_lang(callback)
        user_db_id = user_obj.id if user_obj else None

        if not user_db_id:
            await safe_answer(callback, text=t("search.pagination.user_not_found", lang), show_alert=True)
            return

        # Get vacancies from database
        vacancies, total_found = await get_vacancies_from_db(user_db_id, query)

        if not vacancies:
            await safe_answer(callback, text=t("search.pagination.no_vacancies", lang), show_alert=True)
            return

        # Calculate pagination
        total_pages = (len(vacancies) + VACANCIES_PER_PAGE - 1) // VACANCIES_PER_PAGE

        # Validate page number
        if page < 0 or page >= total_pages:
            await safe_answer(callback, text=t("search.pagination.invalid_page", lang), show_alert=True)
            return

        # Check if user clicked on the current page (extract from message text)
        import re

        current_page_match = re.search(
            r"Страница (\d+) из" if lang == "ru" else r"Page (\d+) of", callback.message.text or ""
        )
        if current_page_match:
            current_page_num = int(current_page_match.group(1)) - 1  # Convert to 0-based
            if current_page_num == page:
                # User clicked on the current page, just answer callback
                await safe_answer(callback)
                return

        # Format page
        response_text = format_search_page(query, vacancies, page, VACANCIES_PER_PAGE, total_found, lang)

        # Create pagination keyboard
        reply_markup = build_search_keyboard(query, page, total_pages, VACANCIES_PER_PAGE, len(vacancies))

        # Update message
        try:
            await callback.message.edit_text(
                response_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=reply_markup,
            )
        except Exception as edit_error:
            # If message is not modified (same content), just answer callback
            if "not modified" in str(edit_error).lower():
                await safe_answer(callback)
                return
            raise

        await safe_answer(callback)
        logger.success(f"Page {page + 1} displayed for user {user_id} for query '{query}'")

    except ValueError as e:
        logger.error(f"Invalid page number in callback: {e}")
        await safe_answer(callback, text=t("search.pagination.invalid_page", lang), show_alert=True)
    except Exception as e:
        logger.error(f"Failed to handle pagination for user {user_id}, query '{query}': {e}")
        await safe_answer(callback, text=t("search.pagination.error_loading", lang), show_alert=True)
