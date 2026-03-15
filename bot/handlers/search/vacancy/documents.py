import asyncio
import html
from collections.abc import Awaitable, Callable

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from bot.db import CVType
from bot.handlers.search.common import format_document_header, safe_answer
from bot.handlers.search.vacancy.prompts import DOCUMENT_META
from bot.services import cv_service, user_service
from bot.services.openai_service import openai_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger
from bot.utils.search import get_vacancies_from_db
from bot.utils.vacancy_docs import sanitize_cover_letter_text

router = Router()
logger = get_logger(__name__)

GENERATION_TIMEOUT = 40  # seconds
DRAFT_UPDATE_INTERVAL = 0.8  # seconds
MAX_DRAFT_TEXT_LENGTH = 4096


async def _parse_callback(
    callback: CallbackQuery, lang: str
) -> tuple[CVType, dict, str, int, str] | None:
    doc_key = "cv"
    doc_type = CVType.CV
    doc_meta = DOCUMENT_META[CVType.CV]
    try:
        if callback.data.startswith("vacancy_doc:"):
            parts = callback.data.split(":", 4)
            if len(parts) != 5:
                await safe_answer(
                    callback,
                    text=t("search.vacancy_detail.invalid_request", lang),
                    show_alert=True,
                )
                return None
            doc_key, query, idx, action = parts[1], parts[2], int(parts[3]), parts[4]
        else:
            parts = callback.data.split(":", 3)
            if len(parts) != 4:
                await safe_answer(
                    callback,
                    text=t("search.vacancy_detail.invalid_request", lang),
                    show_alert=True,
                )
                return None
            query, idx, action = parts[1], int(parts[2]), parts[3]

        doc_type = CVType.COVER_LETTER if doc_key == "cover" else CVType.CV
        doc_meta = DOCUMENT_META.get(doc_type, DOCUMENT_META[CVType.CV])
        return doc_type, doc_meta, query, idx, action
    except ValueError:
        await safe_answer(
            callback,
            text=t("search.vacancy_detail.invalid_request", lang),
            show_alert=True,
        )
        return None


async def _get_user_and_lang(
    callback: CallbackQuery, lang: str
) -> tuple[int | None, object | None, str]:
    user_obj, lang = await user_service.get_or_create_user_with_lang(
        tg_user_id=str(callback.from_user.id),
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        language_code=callback.from_user.language_code,
    )
    user_db_id = user_obj.id if user_obj else None
    return user_db_id, user_obj, lang


async def _get_vacancy(
    user_db_id: int, query: str, idx: int, lang: str, callback: CallbackQuery
) -> dict | None:
    vacancies, _ = await get_vacancies_from_db(user_db_id, query)
    if not vacancies or idx < 0 or idx >= len(vacancies):
        await safe_answer(
            callback, text=t("search.vacancy_detail.not_found", lang), show_alert=True
        )
        return None
    vacancy = vacancies[idx]
    vacancy_db_id = vacancy.get("db_id")
    if not vacancy_db_id:
        await safe_answer(
            callback,
            text=t("search.vacancy_detail.data_incomplete", lang),
            show_alert=True,
        )
        return None
    return vacancy


async def _get_existing_doc(
    user_db_id: int, vacancy_db_id: int, doc_type: CVType
) -> object | None:
    try:
        return await cv_service.get_cv(user_db_id, vacancy_db_id, doc_type)
    except Exception as e:
        logger.error(
            f"Failed to fetch cached doc type={int(doc_type)} for user {user_db_id}: {e}"
        )
        return None


def _build_draft_id(vacancy_db_id: int, doc_type: CVType) -> int:
    return vacancy_db_id * 10 + int(doc_type) + 1


def _build_draft_text(status_text: str, content: str) -> str:
    prefix = f"{status_text}\n\n"
    if len(prefix) >= MAX_DRAFT_TEXT_LENGTH:
        return prefix[:MAX_DRAFT_TEXT_LENGTH]

    available = MAX_DRAFT_TEXT_LENGTH - len(prefix)
    return prefix + content[:available]


async def _stream_document_generation(
    messages,
    doc_meta,
    llm_settings,
    on_partial: Callable[[str], Awaitable[None]] | None = None,
) -> str | None:
    chunks: list[str] = []
    partial_text = ""

    async for chunk in openai_service.chat_completion_stream(
        messages,
        model=openai_service.settings.LLM_MODEL,
        max_tokens=doc_meta["max_tokens"],
        llm_overrides=llm_settings or None,
    ):
        if not chunk:
            continue
        chunks.append(chunk)
        partial_text += chunk
        if on_partial:
            await on_partial(partial_text)

    return "".join(chunks)


@router.callback_query(
    lambda c: c.data.startswith("vacancy_cv:") or c.data.startswith("vacancy_doc:")
)
async def vacancy_cv_handler(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    await safe_answer(callback)
    lang = detect_lang(callback.from_user.language_code if callback.from_user else None)

    try:
        parsed = await _parse_callback(callback, lang)
        if not parsed:
            return
        doc_type, doc_meta, query, idx, action = parsed

        user_db_id, user_obj, lang = await _get_user_and_lang(callback, lang)
        if not user_db_id:
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.user_not_found", lang),
                show_alert=True,
            )
            return

        vacancy = await _get_vacancy(user_db_id, query, idx, lang, callback)
        if not vacancy:
            return
        vacancy_db_id = vacancy["db_id"]

        existing_doc = await _get_existing_doc(user_db_id, vacancy_db_id, doc_type)

        if action in {"send", "generate"} and existing_doc and action != "regen":
            header, _ = format_document_header(vacancy, lang, doc_type)
            escaped = html.escape(existing_doc.text)
            await callback.message.answer(
                f"{header}\n<pre>{escaped}</pre>",
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
            return

        if action == "send" and not existing_doc:
            await safe_answer(
                callback, text=t(doc_meta["no_cache_key"], lang), show_alert=True
            )
            return

        prefs = user_obj.preferences if user_obj and user_obj.preferences else {}
        user_resume = prefs.get("resume")
        user_skills = prefs.get("skills")
        llm_settings = prefs.get("llm_settings") or {}
        user_prompt = None

        if not openai_service._initialized and not (llm_settings.get("api_key")):
            await safe_answer(
                callback,
                text=t("search.vacancy_detail.llm_unavailable", lang),
                show_alert=True,
            )
            return

        candidate_name_parts = [
            part
            for part in [
                (user_obj.first_name if user_obj else None),
                (user_obj.last_name if user_obj else None),
            ]
            if part
        ]
        candidate_name = " ".join(candidate_name_parts) or (
            user_obj.username if user_obj and user_obj.username else None
        )

        messages = doc_meta["prompt_builder"](
            vacancy, user_resume, user_skills, user_prompt, candidate_name, lang
        )
        generating_text = t(doc_meta["generating_key"], lang)
        generating_msg = await callback.message.answer(generating_text)

        draft_enabled = bool(
            callback.message
            and callback.message.chat
            and callback.message.chat.type == "private"
        )
        draft_id = _build_draft_id(vacancy_db_id, doc_type)
        last_draft_sent_at = 0.0
        draft_failed = False

        async def push_draft(partial_text: str) -> None:
            nonlocal last_draft_sent_at, draft_failed
            if not draft_enabled or draft_failed or not callback.message:
                return

            now = asyncio.get_event_loop().time()
            if partial_text and (now - last_draft_sent_at) < DRAFT_UPDATE_INTERVAL:
                return

            try:
                await callback.bot.send_message_draft(
                    chat_id=callback.message.chat.id,
                    draft_id=draft_id,
                    text=_build_draft_text(generating_text, partial_text),
                )
                last_draft_sent_at = now
            except TelegramBadRequest as e:
                draft_failed = True
                logger.warning(
                    f"sendMessageDraft unavailable for chat {callback.message.chat.id}: {e}"
                )
            except Exception as e:
                draft_failed = True
                logger.warning(
                    f"Failed to push message draft for user {user_id}, vacancy {vacancy_db_id}: {e}"
                )

        async def generate_with_draft() -> str | None:
            return await _stream_document_generation(
                messages,
                doc_meta,
                llm_settings,
                on_partial=push_draft if draft_enabled else None,
            )

        try:
            doc_text = await asyncio.wait_for(
                generate_with_draft(), timeout=GENERATION_TIMEOUT
            )
        except TimeoutError:
            logger.error("LLM generation timed out")
            await callback.message.answer(t(doc_meta["failed_key"], lang))
            return

        if not doc_text or not str(doc_text).strip():
            logger.error(
                "LLM returned empty document",
                extra={
                    "user_id": user_id,
                    "vacancy_id": vacancy_db_id,
                    "query": query,
                    "llm_model": openai_service.settings.LLM_MODEL,
                    "doc_type": int(doc_type),
                },
            )
            await callback.message.answer(t(doc_meta["empty_key"], lang))
            return

        try:
            normalized_text = str(doc_text)
            if doc_type == CVType.COVER_LETTER:
                normalized_text = sanitize_cover_letter_text(normalized_text)
            await cv_service.upsert_cv(
                user_db_id, vacancy_db_id, normalized_text, doc_type
            )
            doc_text = normalized_text
        except Exception as e:
            logger.error(
                f"Failed to cache doc type={int(doc_type)} for user {user_db_id}: {e}"
            )

        header, _ = format_document_header(vacancy, lang, doc_type)
        try:
            escaped = html.escape(str(doc_text))
            await generating_msg.edit_text(
                f"{header}\n<pre>{escaped}</pre>",
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
        except Exception:
            await callback.message.answer(
                f"{header}\n<pre>{html.escape(str(doc_text))}</pre>",
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
        logger.error(f"Failed to handle document generation for user {user_id}: {e}")
        try:
            await callback.message.answer(t(doc_meta["failed_key"], lang))
        except Exception:
            await safe_answer(
                callback, text=t(doc_meta["failed_key"], lang), show_alert=True
            )
