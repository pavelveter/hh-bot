from __future__ import annotations

from bot.db.database import db_session
from bot.db.user_repository import UserRepository

CLEAR_COMMANDS = {"clear", "удалить", "сбросить", "none", "null"}


def is_clear_command(raw: str | None) -> bool:
    return (raw or "").strip().lower() in CLEAR_COMMANDS


async def update_user_prefs(tg_id: str, **kwargs):
    """Convenience helper to update user preferences via repository."""
    if not kwargs:
        return
    async with db_session() as session:
        if not session:
            return
        repo = UserRepository(session)
        await repo.update_preferences(tg_id, **kwargs)


async def load_user(tg_id: str):
    async with db_session() as session:
        if not session:
            return None
        repo = UserRepository(session)
        return await repo.get_user_by_tg_id(tg_id)


