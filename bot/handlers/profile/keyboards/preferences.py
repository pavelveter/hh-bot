from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


def preferences_keyboard(has_prompt: bool, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.schedule_time", lang),
                    callback_data="prefs_schedule_time",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.timezone", lang),
                    callback_data="prefs_timezone",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.change_language", lang),
                    callback_data="prefs_lang_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("profile.buttons.back_profile", lang),
                    callback_data="prefs_back_profile",
                ),
            ],
        ]
    )
