from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import SearchQuery
from bot.utils.logging import get_logger

# Create logger for this module
repo_logger = get_logger(__name__)


class SearchQueryRepository:
    """Repository for search query-related database operations"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = repo_logger.bind(repository="SearchQueryRepository")

    async def create_search_query(
        self,
        user_id: int,
        query_text: str,
        search_params: dict = None,
        results_count: int = 0,
        response_time: int = None,
    ) -> SearchQuery:
        """Create a new search query record"""
        try:
            search_query = SearchQuery(
                user_id=user_id,
                query_text=query_text,
                search_params=search_params or {},
                results_count=results_count,
                response_time=response_time,
            )
            self.session.add(search_query)
            await self.session.commit()
            await self.session.refresh(search_query)
            self.logger.info(f"Created search query {search_query.id} for user {user_id}")
            return search_query
        except Exception as e:
            self.logger.error(f"Error creating search query for user {user_id}: {e}")
            await self.session.rollback()
            raise

    async def get_search_queries_by_user(self, user_id: int, limit: int = 10) -> list[SearchQuery]:
        """Get recent search queries for a user"""
        try:
            stmt = (
                select(SearchQuery)
                .where(SearchQuery.user_id == user_id)
                .order_by(SearchQuery.created_at.desc())
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            queries = result.scalars().all()
            self.logger.debug(f"Retrieved {len(queries)} search queries for user {user_id}")
            return queries
        except Exception as e:
            self.logger.error(f"Error getting search queries for user {user_id}: {e}")
            raise

    async def get_latest_search_query(self, user_id: int, query_text: str) -> SearchQuery | None:
        """Get the most recent search query for a user with specific query text"""
        try:
            stmt = (
                select(SearchQuery)
                .where(
                    SearchQuery.user_id == user_id,
                    SearchQuery.query_text == query_text,
                )
                .order_by(SearchQuery.created_at.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            query = result.scalar_one_or_none()
            if query:
                self.logger.debug(
                    f"Retrieved latest search query {query.id} for user {user_id} with query '{query_text}'"
                )
            return query
        except Exception as e:
            self.logger.error(f"Error getting latest search query for user {user_id}: {e}")
            raise

    async def get_latest_search_query_any(self, user_id: int) -> SearchQuery | None:
        """Get the most recent search query for a user (any text)"""
        try:
            stmt = (
                select(SearchQuery)
                .where(SearchQuery.user_id == user_id)
                .order_by(SearchQuery.created_at.desc())
                .limit(1)
            )
            result = await self.session.execute(stmt)
            query = result.scalar_one_or_none()
            if query:
                self.logger.debug(
                    f"Retrieved latest search query {query.id} for user {user_id} (text='{query.query_text}')"
                )
            return query
        except Exception as e:
            self.logger.error(f"Error getting latest search query for user {user_id}: {e}")
            raise
