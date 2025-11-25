"""Database helpers for search results."""

from sqlalchemy import select, update

from bot.db import SearchQueryRepository, UserSearchResultRepository, VacancyRepository
from bot.db.database import get_db_session
from bot.db.models import UserSearchResult, Vacancy
from bot.utils.logging import get_logger
from bot.utils.search.search_cache import cache_vacancies, get_cached_vacancies

logger = get_logger(__name__)


def _normalize_field(value: str | None) -> str | None:
    if not value:
        return None
    if value == "N/A":
        return None
    return value


def extract_vacancy_data(vacancy: dict) -> dict:
    """Extract vacancy data for database storage."""
    employer = vacancy.get("employer", {})
    area = vacancy.get("area", {})
    snippet = vacancy.get("snippet", {})
    salary = vacancy.get("salary") if isinstance(vacancy.get("salary"), dict) else {}
    employment = vacancy.get("employment") if isinstance(vacancy.get("employment"), dict) else {}
    experience = vacancy.get("experience") if isinstance(vacancy.get("experience"), dict) else {}
    schedule = vacancy.get("schedule") if isinstance(vacancy.get("schedule"), dict) else {}

    return {
        "hh_vacancy_id": str(vacancy.get("id", "")),
        "title": vacancy.get("name", "N/A"),
        "company": employer.get("name") if isinstance(employer, dict) else None,
        "location": area.get("name") if isinstance(area, dict) else None,
        "url": vacancy.get("alternate_url"),
        "description": (snippet.get("requirement", "") if isinstance(snippet, dict) else ""),
        "requirements": (snippet.get("responsibility", "") if isinstance(snippet, dict) else ""),
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "salary_currency": salary.get("currency"),
        "employment_type": employment.get("id"),
        "experience": experience.get("id"),
        "schedule": schedule.get("id"),
    }


async def store_search_results(
    user_db_id: int,
    query_text: str,
    vacancies: list[dict],
    response_time: int,
    per_page: int = 100,
) -> bool:
    """Store all search results in database. Duplicates are automatically skipped."""
    db_session = await get_db_session()
    if not db_session:
        logger.warning("Could not get database session for storing search results")
        return False

    try:
        search_repo = SearchQueryRepository(db_session)
        vacancy_repo = VacancyRepository(db_session)
        user_search_result_repo = UserSearchResultRepository(db_session)

        search_query = await search_repo.create_search_query(
            user_id=user_db_id,
            query_text=query_text,
            search_params={"per_page": per_page},
            results_count=len(vacancies),
            response_time=response_time,
        )

        all_vacancy_data = [extract_vacancy_data(vacancy) for vacancy in vacancies]
        hh_vacancy_ids = [v["hh_vacancy_id"] for v in all_vacancy_data]

        existing_vacancies = await vacancy_repo.get_vacancies_by_hh_ids(hh_vacancy_ids)
        existing_ids = set(existing_vacancies.keys())

        new_vacancies_data = [v for v in all_vacancy_data if v["hh_vacancy_id"] not in existing_ids]

        if new_vacancies_data:
            new_vacancies_dict = await vacancy_repo.bulk_create_vacancies(new_vacancies_data)
            existing_vacancies.update(new_vacancies_dict)
        else:
            new_vacancies_dict = {}

        for vacancy_data in all_vacancy_data:
            hh_id = vacancy_data["hh_vacancy_id"]
            if hh_id in existing_ids:
                vac_obj = existing_vacancies.get(hh_id)
                if not vac_obj:
                    continue
                update_fields = {}
                for field in [
                    "title",
                    "company",
                    "location",
                    "url",
                    "description",
                    "requirements",
                    "salary_from",
                    "salary_to",
                    "salary_currency",
                    "employment_type",
                    "experience",
                    "schedule",
                ]:
                    val = vacancy_data.get(field)
                    if val is not None and getattr(vac_obj, field) != val:
                        update_fields[field] = val
                if update_fields:
                    stmt = update(Vacancy).where(Vacancy.hh_vacancy_id == hh_id).values(**update_fields)
                    await db_session.execute(stmt)
        if existing_ids:
            await db_session.commit()

        user_search_results_data = []
        for i, vacancy_data in enumerate(all_vacancy_data, 1):
            hh_id = vacancy_data["hh_vacancy_id"]
            vacancy_obj = existing_vacancies.get(hh_id)
            if vacancy_obj:
                user_search_results_data.append(
                    {
                        "user_id": user_db_id,
                        "search_query_id": search_query.id,
                        "vacancy_id": vacancy_obj.id,
                        "position": i,
                    }
                )

        if user_search_results_data:
            await user_search_result_repo.bulk_create_user_search_results(user_search_results_data)

        new_count = len(new_vacancies_dict)
        existing_count = len(vacancies) - new_count

        logger.info(
            f"Stored search query and {len(vacancies)} results for user {user_db_id} "
            f"(new: {new_count}, existing: {existing_count})"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to store search results for user {user_db_id}: {e}")
        return False
    finally:
        await db_session.close()


async def get_vacancies_from_db(user_db_id: int, query_text: str, use_cache: bool = True) -> tuple[list[dict], int]:
    """Get vacancies from database for a user's search query."""
    if use_cache:
        cached = get_cached_vacancies(user_db_id, query_text)
        if cached is not None:
            return cached

    db_session = await get_db_session()
    if not db_session:
        logger.warning("Could not get database session for retrieving vacancies")
        return [], 0

    try:
        search_repo = SearchQueryRepository(db_session)
        search_query = await search_repo.get_latest_search_query(user_id=user_db_id, query_text=query_text)

        if not search_query:
            logger.warning(f"No search query found for user {user_db_id} with query '{query_text}'")
            return [], 0

        stmt = (
            select(UserSearchResult, Vacancy)
            .join(Vacancy, UserSearchResult.vacancy_id == Vacancy.id)
            .where(UserSearchResult.search_query_id == search_query.id)
            .order_by(UserSearchResult.position)
        )
        result = await db_session.execute(stmt)
        rows = result.all()

        vacancies: list[dict] = []
        for _, vacancy in rows:
            company = _normalize_field(vacancy.company)
            area_name = _normalize_field(vacancy.location)
            url = _normalize_field(vacancy.url)
            vacancies.append(
                {
                    "db_id": vacancy.id,
                    "id": vacancy.hh_vacancy_id,
                    "name": _normalize_field(vacancy.title),
                    "employer": {"name": company} if company else {},
                    "area": {"name": area_name} if area_name else {},
                    "alternate_url": url,
                    "description": _normalize_field(vacancy.description) or "",
                    "requirements": _normalize_field(vacancy.requirements) or "",
                    "employment": {"id": vacancy.employment_type} if vacancy.employment_type else None,
                    "experience": {"id": vacancy.experience} if vacancy.experience else None,
                    "schedule": {"id": vacancy.schedule} if vacancy.schedule else None,
                    "salary": (
                        {
                            "from": vacancy.salary_from,
                            "to": vacancy.salary_to,
                            "currency": vacancy.salary_currency,
                        }
                        if vacancy.salary_from or vacancy.salary_to
                        else None
                    ),
                }
            )

        total_found = search_query.results_count

        if use_cache:
            cache_vacancies(user_db_id, query_text, vacancies, total_found)

        logger.debug(f"Retrieved {len(vacancies)} vacancies from DB for user {user_db_id}, query '{query_text}'")
        return vacancies, total_found

    except Exception as e:
        logger.error(f"Failed to get vacancies from DB for user {user_db_id}: {e}")
        return [], 0
    finally:
        await db_session.close()
