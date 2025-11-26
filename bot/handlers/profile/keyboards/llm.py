from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


def llm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.llm_edit", lang),
                    callback_data="llm_edit",
                )
            ],
            [InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="llm_back_profile")],
        ]
    )
