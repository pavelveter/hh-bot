from __future__ import annotations

from bot.services import user_service

CLEAR_COMMANDS = {"clear", "удалить", "сбросить", "none", "null"}


def is_clear_command(raw: str | None) -> bool:
    return (raw or "").strip().lower() in CLEAR_COMMANDS


async def update_user_prefs(tg_id: str, **kwargs):
    """Convenience helper to update user preferences via repository."""
    if not kwargs:
        return
    await user_service.update_preferences(tg_id, **kwargs)


async def load_user(tg_id: str):
    return await user_service.get_user_by_tg_id(tg_id)


def split_name(raw: str) -> tuple[str | None, str | None, str | None]:
    """Split raw name into first/middle/last with optional middle and last parts."""
    if not raw:
        return None, None, None
    parts = raw.split()
    first = parts[0].strip() if parts else None
    if len(parts) == 1:
        return first, None, None
    if len(parts) == 2:
        return first, None, parts[1].strip()

    middle = parts[1].strip()
    last = " ".join(parts[2:]).strip() or None
    return first, middle, last


def build_full_name(
    first_name: str | None, middle_name: str | None = None, last_name: str | None = None
) -> str:
    return " ".join(part.strip() for part in [first_name, middle_name, last_name] if part and part.strip())
