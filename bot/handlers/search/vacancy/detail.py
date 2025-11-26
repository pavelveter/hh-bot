from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.db import CVRepository, CVType
from bot.db.database import db_session
from bot.handlers.search.common import VACANCIES_PER_PAGE, safe_answer
from bot.handlers.search.helpers import get_or_create_user_lang
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.search import format_vacancy_details, get_vacancies_from_db
from bot.utils.vacancy_docs import ensure_vacancy_db_id

logger = get_logger(__name__)

router = Router()


@router.callback_query(lambda c: c.data.startswith("vacancy_detail:"))
async def vacancy_detail_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = detect_lang(callback.from_user.language_code if callback.from_user else None)

    try:
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await safe_answer(callback, text=t("search.vacancy_detail.invalid_request", lang), show_alert=True)
            return

        query = parts[1]
        idx = int(parts[2])

        user_obj, lang = await get_or_create_user_lang(callback)
        user_db_id = user_obj.id if user_obj else None

        if not user_db_id:
            await safe_answer(callback, text=t("search.vacancy_detail.user_not_found", lang), show_alert=True)
            return

        vacancies, total_found = await get_vacancies_from_db(user_db_id, query)
        if not vacancies or idx < 0 or idx >= len(vacancies):
            await safe_answer(callback, text=t("search.vacancy_detail.not_found", lang), show_alert=True)
            return

        vacancy = vacancies[idx]
        detail_text = format_vacancy_details(vacancy, idx + 1, total_found or len(vacancies), lang)
        page = idx // VACANCIES_PER_PAGE
        vacancy_db_id = await ensure_vacancy_db_id(vacancy)

        cv_buttons: list[InlineKeyboardButton] = []
        cover_buttons: list[InlineKeyboardButton] = []
        preview_blocks: list[str] = []
        if vacancy_db_id and user_db_id:
            cv = None
            cover_letter = None
            async with db_session() as session:
                if session:
                    try:
                        cv_repo = CVRepository(session)
                        cv = await cv_repo.get_cv(user_db_id, vacancy_db_id, CVType.CV)
                        cover_letter = await cv_repo.get_cv(user_db_id, vacancy_db_id, CVType.COVER_LETTER)
                    except Exception as e:
                        logger.error(
                            f"Failed to fetch CV/cover cache for user {user_db_id}, vacancy {vacancy_db_id}: {e}"
                        )

            if cv:
                cv_preview = (cv.text[:400] + "…") if len(cv.text) > 400 else cv.text
                preview_blocks.append(t("search.vacancy_detail.cached_preview", lang).format(preview=cv_preview))
                cv_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.send_cv", lang),
                        callback_data=f"vacancy_doc:cv:{query}:{idx}:send",
                    )
                )
                cv_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.regenerate_cv", lang),
                        callback_data=f"vacancy_doc:cv:{query}:{idx}:regen",
                    )
                )
            else:
                cv_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.generate_cv", lang),
                        callback_data=f"vacancy_doc:cv:{query}:{idx}:generate",
                    )
                )

            if cover_letter:
                cover_preview = (cover_letter.text[:400] + "…") if len(cover_letter.text) > 400 else cover_letter.text
                preview_blocks.append(
                    t("search.vacancy_detail.cached_cover_preview", lang).format(preview=cover_preview)
                )
                cover_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.send_cover_letter", lang),
                        callback_data=f"vacancy_doc:cover:{query}:{idx}:send",
                    )
                )
                cover_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.regenerate_cover_letter", lang),
                        callback_data=f"vacancy_doc:cover:{query}:{idx}:regen",
                    )
                )
            else:
                cover_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.generate_cover_letter", lang),
                        callback_data=f"vacancy_doc:cover:{query}:{idx}:generate",
                    )
                )

        if preview_blocks:
            detail_text += "\n\n" + "\n\n".join(preview_blocks)

        back_button = [
            InlineKeyboardButton(
                text=t("search.vacancy_detail.buttons.back", lang),
                callback_data=f"search_page:{query}:{page}",
            )
        ]
        hh_button = [
            InlineKeyboardButton(
                text=t("search.vacancy_detail.buttons.open_hh", lang),
                url=vacancy.get("alternate_url", "https://hh.ru"),
            )
        ]

        inline_rows = []
        if cv_buttons:
            inline_rows.append(cv_buttons)
        if cover_buttons:
            inline_rows.append(cover_buttons)
        inline_rows.append(back_button)
        inline_rows.append(hh_button)

        back_button_markup = InlineKeyboardMarkup(inline_keyboard=inline_rows)

        await callback.message.edit_text(
            detail_text,
            parse_mode="HTML",
            disable_web_page_preview=False,
            reply_markup=back_button_markup,
        )
        await safe_answer(callback)
        logger.info(f"Sent vacancy detail idx={idx} for user {user_id} query '{query}'")

    except ValueError:
        await safe_answer(callback, text=t("search.vacancy_detail.invalid_id", lang), show_alert=True)
    except Exception as e:
        logger.error(f"Failed to handle vacancy detail for user {user_id}: {e}")
        await safe_answer(callback, text=t("search.vacancy_detail.error_loading", lang), show_alert=True)
