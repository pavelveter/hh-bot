from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import CV
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class CVRepository:
    """Repository for cached CVs per user/vacancy"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cv(self, user_id: int, vacancy_id: int) -> CV | None:
        stmt = select(CV).where(CV.user_id == user_id, CV.vacancy_id == vacancy_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_cv(self, user_id: int, vacancy_id: int, text: str) -> CV:
        existing = await self.get_cv(user_id, vacancy_id)
        if existing:
            stmt = update(CV).where(CV.id == existing.id).values(text=text).returning(CV)
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.scalar_one()

        cv = CV(user_id=user_id, vacancy_id=vacancy_id, text=text)
        self.session.add(cv)
        await self.session.commit()
        await self.session.refresh(cv)
        logger.info(f"Stored CV for user {user_id}, vacancy {vacancy_id}")
        return cv
