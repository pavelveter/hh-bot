from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


def skills_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.edit_skills", lang),
                    callback_data="edit_skills",
                )
            ],
            [InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="skills_back_profile")],
        ]
    )
