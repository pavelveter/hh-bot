from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


def resume_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.resume_edit", lang),
                    callback_data="resume_edit",
                )
            ],
            [InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="resume_back_profile")],
        ]
    )
