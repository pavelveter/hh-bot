"""Caching helpers for search results."""

import time

from bot.utils.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL = 1800  # 30 minutes in seconds

# In-memory cache for search results
# Key: (user_db_id, query_text), Value: (vacancies, total_found, timestamp)
_search_cache: dict[tuple[int, str], tuple[list[dict], int, float]] = {}


def _cleanup_cache():
    """Remove expired cache entries."""
    current_time = time.time()
    expired_keys = [key for key, (_, _, timestamp) in _search_cache.items() if current_time - timestamp > CACHE_TTL]
    for key in expired_keys:
        del _search_cache[key]
    if expired_keys:
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def get_cached_vacancies(user_db_id: int, query_text: str) -> tuple[list[dict], int] | None:
    """Get cached vacancies if available. Returns None if not cached or expired."""
    _cleanup_cache()
    key = (user_db_id, query_text)
    if key in _search_cache:
        vacancies, total_found, timestamp = _search_cache[key]
        if time.time() - timestamp <= CACHE_TTL:
            logger.debug(f"Cache hit for user {user_db_id}, query '{query_text}' ({len(vacancies)} vacancies)")
            return vacancies, total_found
        # Expired
        del _search_cache[key]
        logger.debug(f"Cache expired for user {user_db_id}, query '{query_text}'")
    return None


def cache_vacancies(user_db_id: int, query_text: str, vacancies: list[dict], total_found: int):
    """Cache search results."""
    key = (user_db_id, query_text)
    _search_cache[key] = (vacancies, total_found, time.time())
    logger.debug(f"Cached {len(vacancies)} vacancies for user {user_db_id}, query '{query_text}'")
