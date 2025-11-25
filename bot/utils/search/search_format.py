"""Formatting helpers for search responses."""

from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)


def format_salary(salary: dict | None, lang: str) -> str:
    """Format salary information from HH API response."""
    if not salary:
        return t("search.salary.not_specified", lang)

    from_str = salary.get("from")
    to_str = salary.get("to")
    currency = salary.get("currency", "")

    if from_str and to_str:
        return t("search.salary.range", lang).format(salary_from=from_str, salary_to=to_str, currency=currency)
    if from_str:
        return t("search.salary.from_only", lang).format(salary_from=from_str, currency=currency)
    if to_str:
        return t("search.salary.to_only", lang).format(salary_to=to_str, currency=currency)
    return t("search.salary.not_specified", lang)


def format_vacancy(vacancy: dict, position: int, lang: str) -> str:
    """Format a single vacancy for display."""
    fallback = t("search.common.not_available", lang)
    name = vacancy.get("name") or fallback

    employer = vacancy.get("employer", {})
    company = employer.get("name") if isinstance(employer, dict) else None
    company = company or fallback

    salary_str = format_salary(vacancy.get("salary"), lang)

    area = vacancy.get("area", {})
    location = area.get("name") if isinstance(area, dict) else None
    location = location or fallback

    url = vacancy.get("alternate_url") or "https://hh.ru"

    return (
        f"{position}. <b>{name}</b>\n"
        f"{t('search.vacancy_card.company', lang).format(company=company)}\n"
        f"{t('search.vacancy_card.salary', lang).format(salary=salary_str)}\n"
        f"{t('search.vacancy_card.location', lang).format(location=location)}\n"
        f"{t('search.vacancy_card.link', lang).format(url=url)}\n\n"
    )


def format_vacancy_details(vacancy: dict, position: int, total_found: int, lang: str) -> str:
    """Format detailed view for a single vacancy."""
    fallback = t("search.common.not_available", lang)
    name = vacancy.get("name") or fallback
    employer = vacancy.get("employer", {})
    company = employer.get("name") if isinstance(employer, dict) else None
    company = company or fallback
    salary_str = format_salary(vacancy.get("salary"), lang)
    area = vacancy.get("area", {})
    location = area.get("name") if isinstance(area, dict) else None
    location = location or fallback
    url = vacancy.get("alternate_url") or "https://hh.ru"
    description = vacancy.get("description") or vacancy.get("snippet", {}).get("requirement", "")
    requirements = vacancy.get("requirements") or vacancy.get("snippet", {}).get("responsibility", "")

    body_parts = []
    if description:
        body_parts.append(description)
    if requirements and requirements not in body_parts:
        body_parts.append(requirements)
    body_text = "\n".join(body_parts) if body_parts else t("search.vacancy_detail.no_description", lang)

    return (
        f"{t('search.vacancy_detail.title', lang).format(position=position, total=total_found)}\n\n"
        f"<b>{name}</b>\n"
        f"{t('search.vacancy_detail.company', lang).format(company=company)}\n"
        f"{t('search.vacancy_detail.salary', lang).format(salary=salary_str)}\n"
        f"{t('search.vacancy_detail.location', lang).format(location=location)}\n"
        f"{t('search.vacancy_detail.link', lang).format(url=url)}\n\n"
        f"{body_text}"
    )


def format_search_page(query: str, vacancies: list[dict], page: int, per_page: int, total_found: int, lang: str) -> str:
    """Format a single page of search results."""
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_vacancies = vacancies[start_idx:end_idx]

    response = t("search.results_header", lang).format(total=total_found, query=query) + "\n\n"

    for i, vacancy in enumerate(page_vacancies, 1):
        global_position = start_idx + i
        response += format_vacancy(vacancy, global_position, lang)

    total_pages = (len(vacancies) + per_page - 1) // per_page
    response += "\n" + t("search.page_label", lang).format(current=page + 1, total=total_pages)

    return response


def format_search_response(query: str, results: dict, lang: str, max_results: int = 3) -> str:
    """Format search results into a response message (legacy function, kept for compatibility)."""
    vacancies = results.get("items", [])
    found_count = results.get("found", 0)

    response = t("search.results_header", lang).format(total=found_count, query=query) + "\n\n"

    for i, vacancy in enumerate(vacancies[:max_results], 1):
        response += format_vacancy(vacancy, i, lang)

    more_url = f"https://hh.ru/search/vacancy?text={query}"
    response += t("search.more_results", lang).format(url=more_url)
    return response


def create_pagination_keyboard(query: str, page: int, total_pages: int) -> list[list[dict[str, str]]]:
    """Create inline keyboard for pagination with page numbers and ellipsis."""
    keyboard = []
    buttons = []

    # Previous
    if page > 0:
        buttons.append({"text": "◀️", "callback_data": f"search_page:{query}:{page - 1}"})

    current_page_num = page + 1

    if total_pages <= 7:
        for p in range(1, total_pages + 1):
            text = f"• {p} •" if p == current_page_num else str(p)
            buttons.append({"text": text, "callback_data": f"search_page:{query}:{p - 1}"})
    else:
        start_page = max(2, current_page_num - 1)
        end_page = min(total_pages - 1, current_page_num + 1)

        buttons.append({"text": ("• 1 •" if current_page_num == 1 else "1"), "callback_data": f"search_page:{query}:0"})
        if start_page > 2:
            buttons.append({"text": "...", "callback_data": "noop"})

        for p in range(start_page, end_page + 1):
            if p in {1, total_pages}:
                continue
            text = f"• {p} •" if p == current_page_num else str(p)
            buttons.append({"text": text, "callback_data": f"search_page:{query}:{p - 1}"})

        if end_page < total_pages - 1:
            buttons.append({"text": "...", "callback_data": "noop"})

        if total_pages > 1:
            text = f"• {total_pages} •" if current_page_num == total_pages else str(total_pages)
            buttons.append({"text": text, "callback_data": f"search_page:{query}:{total_pages - 1}"})

    if page < total_pages - 1:
        buttons.append({"text": "▶️", "callback_data": f"search_page:{query}:{page + 1}"})

    if buttons:
        keyboard.append(buttons)

    return keyboard


def create_vacancy_buttons(query: str, page: int, per_page: int, total_count: int) -> list[dict[str, str]]:
    """Create row of buttons for vacancies on the current page, showing absolute indices."""
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total_count)
    return [{"text": str(i + 1), "callback_data": f"vacancy_detail:{query}:{i}"} for i in range(start_idx, end_idx)]
