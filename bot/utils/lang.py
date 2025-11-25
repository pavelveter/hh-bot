from bot.db.database import get_db_session
from bot.db.user_repository import UserRepository
from bot.utils.i18n import detect_lang


async def resolve_lang(tg_id: str, fallback_code: str | None) -> str:
    """Resolve language with preference to stored user language."""
    lang = detect_lang(fallback_code)
    async with await get_db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id)
    if user and user.language_code:
        return detect_lang(user.language_code)
    return lang
