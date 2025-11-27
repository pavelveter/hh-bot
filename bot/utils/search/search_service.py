"""Search execution helpers (HH API wrapper)."""

import asyncio
import time

from bot.services.hh_service import hh_service
from bot.utils.logging import get_logger

logger = get_logger(__name__)


async def perform_search(
    query: str,
    per_page: int = 100,
    max_pages: int | None = None,
    search_in_name_only: bool = True,
    area_id: str | None = None,
    filters: dict | None = None,
) -> tuple[dict | None, int]:
    """Perform search and return all results with response time."""
    start_time = time.time()
    all_items: list[dict] = []
    total_found = 0
    page = 0
    pages_count = 0
    max_retries = 3
    retry_delay = 2  # seconds

    while True:
        if max_pages and page >= max_pages:
            break

        retries = 0
        page_results = None

        while retries < max_retries:
            try:
                min_salary = filters.get("min_salary") if filters else None
                remote_only = filters.get("remote_only") if filters else None
                freshness_days = filters.get("freshness_days") if filters else None
                employment = filters.get("employment") if filters else None
                experience = filters.get("experience") if filters else None

                page_results = await hh_service.search_vacancies(
                    query,
                    area=area_id,
                    page=page,
                    per_page=per_page,
                    search_in_name_only=search_in_name_only,
                    min_salary=min_salary,
                    remote_only=remote_only,
                    freshness_days=freshness_days,
                    employment=employment,
                    experience=experience,
                )
                if page_results:
                    break
                retries += 1
                if retries < max_retries:
                    logger.warning(
                        f"Failed to fetch page {page} (attempt {retries}/{max_retries}), retrying..."
                    )
                    await asyncio.sleep(retry_delay * retries)
            except Exception as e:
                logger.warning(
                    f"Exception fetching page {page} (attempt {retries + 1}/{max_retries}): {e}"
                )
                retries += 1
                if retries < max_retries:
                    await asyncio.sleep(retry_delay * retries)
                else:
                    logger.error(
                        f"Failed to fetch page {page} after {max_retries} attempts"
                    )
                    break

        if not page_results:
            logger.warning(f"Could not fetch page {page}, stopping pagination")
            break

        items = page_results.get("items", [])
        if not items:
            break

        all_items.extend(items)

        if page == 0:
            total_found = page_results.get("found", 0)
            pages_count = page_results.get("pages", 0)

        if pages_count and page >= pages_count - 1:
            break

        page += 1
        await asyncio.sleep(0.5)

    response_time = int((time.time() - start_time) * 1000)

    combined_results = {
        "items": all_items,
        "found": total_found,
        "pages": pages_count if pages_count else (page + 1),
    }

    logger.info(
        f"Search completed: found {total_found} total, fetched {len(all_items)} items in {response_time}ms"
    )

    return combined_results, response_time
