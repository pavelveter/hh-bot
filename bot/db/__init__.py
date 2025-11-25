"""Database repositories module"""

from bot.db.cv_repository import CVRepository
from bot.db.search_query_repository import SearchQueryRepository
from bot.db.user_repository import UserRepository
from bot.db.user_search_result_repository import UserSearchResultRepository
from bot.db.vacancy_repository import VacancyRepository

__all__ = [
    "UserRepository",
    "SearchQueryRepository",
    "VacancyRepository",
    "UserSearchResultRepository",
    "CVRepository",
]
