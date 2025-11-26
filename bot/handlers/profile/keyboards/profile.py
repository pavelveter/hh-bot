from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


def profile_keyboard(lang: str, skills_count: int = 0, skills_preview: str | None = None) -> InlineKeyboardMarkup:
    skills_button_label = t("profile.buttons.skills_menu", lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("profile.buttons.edit_name", lang), callback_data="edit_name"),
                InlineKeyboardButton(text=t("profile.buttons.edit_city", lang), callback_data="edit_city"),
            ],
            [
                InlineKeyboardButton(text=t("profile.buttons.edit_position", lang), callback_data="edit_position"),
                InlineKeyboardButton(
                    text=skills_button_label,
                    callback_data="skills_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_resume", lang),
                    callback_data="resume_menu",
                ),
                InlineKeyboardButton(
                    text=t("profile.buttons.llm_settings", lang),
                    callback_data="llm_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.search_settings", lang),
                    callback_data="search_settings",
                ),
                InlineKeyboardButton(text=t("profile.buttons.preferences", lang), callback_data="prefs_menu"),
            ],
        ]
    )
