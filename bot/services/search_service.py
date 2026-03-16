from __future__ import annotations

from bot.db.database import db_session
from bot.db.search_query_repository import SearchQueryRepository


async def get_latest_search_query_any(user_id: int, session=None):
    if session:
        repo = SearchQueryRepository(session)
        return await repo.get_latest_search_query_any(user_id)
    async with db_session() as session_cm:
        if not session_cm:
            return None
        repo = SearchQueryRepository(session_cm)
        return await repo.get_latest_search_query_any(user_id)


async def get_recent_distinct_search_queries(
    user_id: int, limit: int = 50, session=None
):
    if session:
        repo = SearchQueryRepository(session)
        return await repo.get_recent_distinct_search_queries(user_id, limit=limit)
    async with db_session() as session_cm:
        if not session_cm:
            return []
        repo = SearchQueryRepository(session_cm)
        return await repo.get_recent_distinct_search_queries(user_id, limit=limit)


async def create_search_query(
    user_id: int,
    query_text: str,
    results_count: int = 0,
    response_time: int | None = None,
    session=None,
):
    if session:
        repo = SearchQueryRepository(session)
        return await repo.create_search_query(
            user_id=user_id,
            query_text=query_text,
            results_count=results_count,
            response_time=response_time,
        )
    async with db_session() as session_cm:
        if not session_cm:
            return None
        repo = SearchQueryRepository(session_cm)
        return await repo.create_search_query(
            user_id=user_id,
            query_text=query_text,
            results_count=results_count,
            response_time=response_time,
        )


async def get_latest_search_query(user_id: int, query_text: str, session=None):
    if session:
        repo = SearchQueryRepository(session)
        return await repo.get_latest_search_query(
            user_id=user_id, query_text=query_text
        )
    async with db_session() as session_cm:
        if not session_cm:
            return None
        repo = SearchQueryRepository(session_cm)
        return await repo.get_latest_search_query(
            user_id=user_id, query_text=query_text
        )
