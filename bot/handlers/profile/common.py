import html

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t
from bot.utils.logging import get_logger

logger = get_logger(__name__)

CANCEL_COMMANDS = {
    "/cancel",
    "cancel",
    "/exit",
    "exit",
    "/отмена",
    "отмена",
    "/выход",
    "выход",
}


class EditProfile(StatesGroup):
    city = State()
    position = State()
    name = State()
    skills = State()
    resume = State()
    llm = State()


class EditSearchFilters(StatesGroup):
    min_salary = State()


class EditPreferences(StatesGroup):
    llm_prompt = State()
    language = State()


def short(text: str | None, lang: str, limit: int = 500, truncated_key: str = "profile.resume_truncated") -> str:
    if not text:
        return t("profile.not_set", lang)
    text = html.escape(text.strip())
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n" + t(truncated_key, lang)


def hide_key(key: str | None) -> str:
    if not key:
        return "not set"
    if len(key) < 6:
        return "***"
    return key[:3] + "***" + key[-2:]


def normalize_skills(raw: str) -> list[str]:
    """Convert mixed-format skill text (bullets/commas/newlines) into a clean list."""
    cleaned = raw.replace("•", "\n").replace("·", "\n").replace(";", ",").replace("—", "\n").replace("–", "\n")

    # Split on comma or newline
    parts: list[str] = []
    for chunk in cleaned.split("\n"):
        parts.extend(chunk.split(","))

    skills: list[str] = []
    seen = set()
    for part in parts:
        item = part.strip()
        item = item.lstrip("-*•·–— ").strip()  # remove bullet markers
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        skills.append(item)
    return skills


def format_search_filters(filters: dict | None, lang: str) -> str:
    filters = filters or {}
    min_salary = filters.get("min_salary")
    remote = filters.get("remote_only")
    freshness = filters.get("freshness_days")
    employment = filters.get("employment")
    experience = filters.get("experience")

    return (
        t("profile.search_filters.min_salary", lang).format(
            value=min_salary if min_salary else t("profile.not_set", lang)
        )
        + "\n"
        + t("profile.search_filters.remote", lang).format(
            state=t("profile.on", lang) if remote else t("profile.off", lang)
        )
        + "\n"
        + t("profile.search_filters.freshness", lang).format(value=freshness or t("profile.not_set", lang))
        + "\n"
        + t("profile.search_filters.employment", lang).format(value=employment or t("profile.not_set", lang))
        + "\n"
        + t("profile.search_filters.experience", lang).format(value=experience or t("profile.not_set", lang))
    )


def search_settings_keyboard(filters: dict | None, lang: str) -> InlineKeyboardMarkup:
    remote = bool(filters.get("remote_only")) if filters else False

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.set_salary", lang),
                    callback_data="search_set_salary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.remote", lang).format(
                        state=(t("profile.on_tick", lang) if remote else t("profile.off", lang))
                    ),
                    callback_data="search_toggle_remote",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.fresh_off", lang),
                    callback_data="search_freshness:clear",
                ),
                InlineKeyboardButton(text="1d", callback_data="search_freshness:1"),
                InlineKeyboardButton(text="2d", callback_data="search_freshness:2"),
                InlineKeyboardButton(text="3d", callback_data="search_freshness:3"),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.employment", lang),
                    callback_data="search_employment_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.experience", lang),
                    callback_data="search_experience_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.clear_filters", lang),
                    callback_data="search_clear_filters",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.back_profile", lang),
                    callback_data="search_back_profile",
                )
            ],
        ]
    )


def employment_keyboard(current: str | None, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    labels = {
        "full": t("profile.employment.full", lang),
        "part": t("profile.employment.part", lang),
        "project": t("profile.employment.project", lang),
        "volunteer": t("profile.employment.volunteer", lang),
        "probation": t("profile.employment.probation", lang),
    }
    for key, label in labels.items():
        marker = "(current) " if key == current else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{label}",
                    callback_data=f"search_set_employment:{key}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=t("profile.buttons.clear_employment", lang),
                callback_data="search_set_employment:clear",
            )
        ]
    )
    buttons.append([InlineKeyboardButton(text=t("profile.buttons.back", lang), callback_data="search_settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def experience_keyboard(current: str | None, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    labels = {
        "no_experience": t("profile.experience.no_experience", lang),
        "between1And3": t("profile.experience.between1And3", lang),
        "between3And6": t("profile.experience.between3And6", lang),
        "moreThan6": t("profile.experience.moreThan6", lang),
    }
    for key, label in labels.items():
        marker = "(current) " if key == current else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{label}",
                    callback_data=f"search_set_experience:{key}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=t("profile.buttons.clear_experience", lang),
                callback_data="search_set_experience:clear",
            )
        ]
    )
    buttons.append([InlineKeyboardButton(text=t("profile.buttons.back", lang), callback_data="search_settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def preferences_keyboard(has_prompt: bool, lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=t("profile.buttons.edit_llm_prompt", lang),
                callback_data="prefs_edit_llm_prompt",
            ),
            InlineKeyboardButton(
                text=t("profile.buttons.clear_llm_prompt", lang),
                callback_data="prefs_clear_llm_prompt",
            ),
        ]
    ]
    if has_prompt:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.change_language", lang),
                    callback_data="prefs_lang_menu",
                ),
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=t("profile.buttons.back_profile", lang),
                callback_data="prefs_back_profile",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("profile.buttons.edit_name", lang), callback_data="edit_name"),
                InlineKeyboardButton(text=t("profile.buttons.edit_city", lang), callback_data="edit_city"),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_position", lang),
                    callback_data="edit_position",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_skills", lang),
                    callback_data="edit_skills",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_resume", lang),
                    callback_data="edit_resume",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.llm_settings", lang),
                    callback_data="edit_llm",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.search_settings", lang),
                    callback_data="search_settings",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.preferences", lang),
                    callback_data="prefs_menu",
                ),
            ],
        ]
    )
