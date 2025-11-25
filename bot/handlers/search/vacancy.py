from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.db import CVRepository, UserRepository
from bot.db.database import get_db_session
from bot.handlers.search.common import (
    VACANCIES_PER_PAGE,
    format_cv_header,
    safe_answer,
)
from bot.services.openai_service import openai_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.prompt_loader import load_prompt
from bot.utils.search import (
    format_vacancy_details,
    get_vacancies_from_db,
)

logger = get_logger(__name__)

router = Router()


@router.callback_query(lambda c: c.data.startswith("vacancy_detail:"))
async def vacancy_detail_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    lang = detect_lang(callback.from_user.language_code if callback.from_user else None)

    try:
        # Parse callback data: vacancy_detail:query:idx
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.invalid_request", lang),
                show_alert=True,
            )
            return

        query = parts[1]
        idx = int(parts[2])

        db_session = await get_db_session()
        user_db_id = None
        if db_session:
            try:
                user_repo = UserRepository(db_session)
                user = await user_repo.get_or_create_user(
                    tg_user_id=user_id,
                    username=callback.from_user.username,
                    first_name=callback.from_user.first_name,
                    last_name=callback.from_user.last_name,
                    language_code=callback.from_user.language_code,
                )
                lang = detect_lang(user.language_code)
                user_db_id = user.id
            except Exception as e:
                logger.error(f"Failed to get user {user_id} from database: {e}")
            finally:
                await db_session.close()

        if not user_db_id:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.user_not_found", lang),
                show_alert=True,
            )
            return

        vacancies, total_found = await get_vacancies_from_db(user_db_id, query)
        if not vacancies or idx < 0 or idx >= len(vacancies):
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.not_found", lang),
                show_alert=True,
            )
            return

        vacancy = vacancies[idx]
        detail_text = format_vacancy_details(vacancy, idx + 1, total_found or len(vacancies), lang)
        page = idx // VACANCIES_PER_PAGE
        vacancy_db_id = vacancy.get("db_id")

        cv_buttons = []
        if vacancy_db_id and user_db_id:
            # Load cached CV
            db_session = await get_db_session()
            cv = None
            if db_session:
                try:
                    cv_repo = CVRepository(db_session)
                    cv = await cv_repo.get_cv(user_db_id, vacancy_db_id)
                except Exception as e:
                    logger.error(f"Failed to fetch CV cache for user {user_db_id}, vacancy {vacancy_db_id}: {e}")
                finally:
                    await db_session.close()

            if cv:
                cv_preview = (cv.text[:400] + "…") if len(cv.text) > 400 else cv.text
                detail_text += "\n\n" + t("search.vacancy_detail.cached_preview", lang).format(preview=cv_preview)
                cv_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.send_cv", lang),
                        callback_data=f"vacancy_cv:{query}:{idx}:send",
                    )
                )
                cv_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.regenerate_cv", lang),
                        callback_data=f"vacancy_cv:{query}:{idx}:regen",
                    )
                )
            else:
                cv_buttons.append(
                    InlineKeyboardButton(
                        text=t("search.vacancy_detail.buttons.generate_cv", lang),
                        callback_data=f"vacancy_cv:{query}:{idx}:generate",
                    )
                )

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
        await safe_answer(
            callback,
            text=t("search.vacancy_detail.error_loading", lang),
            show_alert=True,
        )


def build_cv_prompt(
    vacancy: dict,
    user_resume: str | None,
    user_skills: list[str] | None,
    user_prompt: str | None = None,
    lang: str = "en",
) -> list[dict[str, str]]:
    vacancy_text = format_vacancy_details(vacancy, 1, 1, lang)
    skills_text = ", ".join(user_skills or [])
    resume_text = user_resume or ""

    prompt_template = load_prompt("cv_prompt")
    extra = f"\nДополнительные требования пользователя: {user_prompt}" if user_prompt else ""
    prompt = prompt_template.format(user_prompt_extra=extra)

    user_context = f"Навыки пользователя: {skills_text}" if skills_text else "Навыки пользователя: не указаны"
    if resume_text:
        user_context += f"\nБазовое резюме пользователя:\n{resume_text}"

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Вакансия:\n{vacancy_text}\n\n{user_context}"},
    ]


@router.callback_query(lambda c: c.data.startswith("vacancy_cv:"))
async def vacancy_cv_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    db_session = None
    # Answer early to avoid Telegram callback timeout
    await safe_answer(callback)
    lang = detect_lang(callback.from_user.language_code if callback.from_user else None)

    try:
        # vacancy_cv:query:idx:action
        parts = callback.data.split(":", 3)
        if len(parts) != 4:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.invalid_request", lang),
                show_alert=True,
            )
            return

        query = parts[1]
        idx = int(parts[2])
        action = parts[3]

        db_session = await get_db_session()
        user_db_id = None
        user_obj = None
        if db_session:
            try:
                user_repo = UserRepository(db_session)
                user_obj = await user_repo.get_or_create_user(
                    tg_user_id=user_id,
                    username=callback.from_user.username,
                    first_name=callback.from_user.first_name,
                    last_name=callback.from_user.last_name,
                    language_code=callback.from_user.language_code,
                )
                lang = detect_lang(user_obj.language_code)
                user_db_id = user_obj.id
            except Exception as e:
                logger.error(f"Failed to get user {user_id} from database: {e}")
            finally:
                await db_session.close()

        if not user_db_id:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.user_not_found", lang),
                show_alert=True,
            )
            return

        vacancies, _ = await get_vacancies_from_db(user_db_id, query)
        if not vacancies or idx < 0 or idx >= len(vacancies):
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.not_found", lang),
                show_alert=True,
            )
            return

        vacancy = vacancies[idx]
        vacancy_db_id = vacancy.get("db_id")
        if not vacancy_db_id:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.data_incomplete", lang),
                show_alert=True,
            )
            return

        db_session = await get_db_session()
        cv_repo = CVRepository(db_session) if db_session else None
        existing_cv = None
        if cv_repo:
            try:
                existing_cv = await cv_repo.get_cv(user_db_id, vacancy_db_id)
            except Exception as e:
                logger.error(f"Failed to fetch cached CV for user {user_db_id}: {e}")

        # Handle send without regenerate
        if action in {"send", "generate"} and existing_cv and action != "regen":
            header, _ = format_cv_header(vacancy, lang)
            await callback.message.answer(
                f"{header}\n\n{existing_cv.text}",
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
            if db_session:
                await db_session.close()
            return

        if action == "send" and not existing_cv:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.cv_no_cache", lang),
                show_alert=True,
            )
            if db_session:
                await db_session.close()
            return

        # Need to generate (either regen or first time)
        prefs = user_obj.preferences if user_obj and user_obj.preferences else {}
        user_resume = prefs.get("resume")
        user_skills = prefs.get("skills")
        llm_settings = prefs.get("llm_settings") or {}
        user_prompt = prefs.get("llm_prompt")

        if not openai_service._initialized and not (llm_settings.get("api_key")):
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.llm_unavailable", lang),
                show_alert=True,
            )
            if db_session:
                await db_session.close()
            return

        messages = build_cv_prompt(vacancy, user_resume, user_skills, user_prompt, lang)
        await safe_answer(callback, text=t("search.vacancy_detail.generating", lang), show_alert=False)
        cv_text = await openai_service.chat_completion(
            messages,
            model=openai_service.settings.LLM_MODEL,
            max_tokens=700,
            llm_overrides=llm_settings or None,
        )

        if not cv_text or not cv_text.strip():
            logger.error(
                "LLM returned empty CV",
                extra={
                    "user_id": user_id,
                    "vacancy_id": vacancy_db_id,
                    "query": query,
                    "llm_model": openai_service.settings.LLM_MODEL,
                },
            )
            await callback.message.answer(t("search.vacancy_detail.cv_empty", lang))
            if db_session:
                await db_session.close()
            return

        if cv_repo:
            try:
                await cv_repo.upsert_cv(user_db_id, vacancy_db_id, cv_text)
            except Exception as e:
                logger.error(f"Failed to cache CV for user {user_db_id}: {e}")

        header, _ = format_cv_header(vacancy, lang)
        await callback.message.answer(
            f"{header}\n\n{cv_text}",
            disable_web_page_preview=True,
            parse_mode="HTML",
        )
    except ValueError:
        await safe_answer(
            callback,
            text=t("search.vacancy_detail.invalid_request", lang),
            show_alert=True,
        )
    except Exception as e:
        logger.error(f"Failed to handle CV generation for user {user_id}: {e}")
        await safe_answer(callback, text=t("search.vacancy_detail.cv_failed", lang), show_alert=True)
    finally:
        try:
            if db_session:
                await db_session.close()
        except Exception as close_err:
            logger.warning(f"Failed to close DB session after CV handler: {close_err}")
