import html

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from bot.utils.i18n import t
from bot.utils.logging import get_logger
from bot.utils.search import create_pagination_keyboard, create_vacancy_buttons

logger = get_logger(__name__)


VACANCIES_PER_PAGE = 8


def build_search_keyboard(query: str, page: int, total_pages: int, per_page: int, total_count: int):
    keyboard: list[list[dict[str, str]]] = []
    vacancy_row = create_vacancy_buttons(query, page, per_page, total_count)
    if vacancy_row:
        keyboard.append(vacancy_row)
    pagination_row = create_pagination_keyboard(query, page, total_pages)
    if pagination_row:
        keyboard.extend(pagination_row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None


def format_cv_header(vacancy: dict, lang: str) -> tuple[str, str]:
    url = vacancy.get("alternate_url", "https://hh.ru")
    employer = vacancy.get("employer", {}) if isinstance(vacancy.get("employer"), dict) else {}
    company = employer.get("name") if isinstance(employer, dict) else None
    company_safe = html.escape(company) if company else t("search.common.vacancy_placeholder", lang)
    link_text = t("search.vacancy_detail.cv_header", lang).format(company=company_safe)
    header = f'📄 <a href="{url}">{link_text}</a>:'
    return header, url


async def safe_answer(callback, **kwargs):
    try:
        await callback.answer(**kwargs)
    except TelegramBadRequest as e:
        logger.warning(f"Callback answer failed (probably expired): {e}")
    except Exception as e:
        logger.error(f"Failed to answer callback: {e}")
