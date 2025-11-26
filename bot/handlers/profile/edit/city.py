import html

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from bot.db.database import db_session
from bot.db.user_repository import UserRepository
from bot.handlers.profile.states import EditProfile
from bot.services.hh_service import hh_service
from bot.utils.i18n import t
from bot.utils.lang import resolve_lang
from bot.utils.logging import get_logger

logger = get_logger(__name__)
router = Router()


def _update_city_history(history: list[dict] | None, city: str, area_id: str | None, limit: int = 5) -> list[dict]:
    history = history or []
    normalized_key = (city or "").strip().lower()
    area_key = (area_id or "").strip()
    filtered = [
        item
        for item in history
        if item.get("city", "").strip().lower() != normalized_key or (item.get("area_id") or "") != area_key
    ]
    filtered.insert(0, {"city": city, "area_id": area_id})
    return filtered[:limit]


async def send_city_menu(
    message_obj: types.Message | types.CallbackQuery,
    lang: str,
    edit: bool = False,
    chat_id: int | None = None,
    message_id: int | None = None,
):
    tg_id = str(message_obj.from_user.id) if message_obj.from_user else None
    async with db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(tg_id) if tg_id else None

    if not user:
        target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
        await target.answer(t("profile.no_profile", lang))
        if isinstance(message_obj, types.CallbackQuery):
            await message_obj.answer()
        return

    prefs = user.preferences or {}
    history = prefs.get("city_history") or []
    current_city = html.escape(user.city) if user.city else t("profile.not_set", lang)
    buttons: list[list[types.InlineKeyboardButton]] = []

    for idx, item in enumerate(history[:5]):
        city_label = item.get("city")
        if not city_label:
            continue
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=city_label,
                    callback_data=f"city_pick:{idx}",
                )
            ]
        )

    buttons.append(
        [
            types.InlineKeyboardButton(
                text=t("profile.buttons.city_enter", lang),
                callback_data="city_enter",
            )
        ]
    )
    buttons.append(
        [types.InlineKeyboardButton(text=t("profile.buttons.back_profile", lang), callback_data="city_back")]
    )

    text = (
        t("profile.edit_city_menu", lang, current_city=current_city)
        if history
        else t("profile.edit_city_menu_empty", lang, current_city=current_city)
    )

    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    target = message_obj.message if isinstance(message_obj, types.CallbackQuery) else message_obj
    bot = getattr(message_obj, "bot", None)

    if message_id and bot and chat_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=markup,
            )
            if isinstance(message_obj, types.CallbackQuery):
                await message_obj.answer()
            return
        except Exception as e:
            logger.debug(f"Failed to edit city menu by id: {e}")

    if isinstance(message_obj, types.CallbackQuery):
        try:
            if edit:
                await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
            else:
                await target.answer(text, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.debug(f"Failed to edit city menu message: {e}")
            await target.answer(text, parse_mode="HTML", reply_markup=markup)
        finally:
            await message_obj.answer()
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "edit_city")
async def cb_edit_city(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    await send_city_menu(call, lang, edit=True)


@router.callback_query(F.data == "city_enter")
async def cb_city_enter(call: types.CallbackQuery, state: FSMContext):
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    prompt = await call.message.answer(t("profile.edit_city_prompt", lang))
    await state.update_data(
        city_menu_chat_id=call.message.chat.id,
        city_menu_message_id=call.message.message_id,
        city_prompt_message_id=prompt.message_id,
    )
    await state.set_state(EditProfile.city)
    await call.answer()


@router.callback_query(F.data == "city_back")
async def cb_city_back(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    from bot.handlers.profile.view import send_profile_view

    await send_profile_view(str(call.from_user.id), call.message, edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("city_pick:"))
async def cb_city_pick(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await resolve_lang(str(call.from_user.id), call.from_user.language_code if call.from_user else None)
    try:
        idx = int(call.data.split(":")[1])
    except Exception:
        await call.answer()
        return

    async with db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(str(call.from_user.id))

        if not user:
            await call.message.answer(t("profile.no_profile", lang))
            await call.answer()
            return

        prefs = user.preferences or {}
        history = prefs.get("city_history") or []
        if idx >= len(history) or idx < 0:
            await call.message.answer(t("profile.edit_city_not_found", lang).format(city=""))
            await call.answer()
            return

        item = history[idx]
        city = item.get("city")
        area_id = item.get("area_id")
        if not city or not area_id:
            await call.message.answer(t("profile.edit_city_prompt", lang))
            await state.set_state(EditProfile.city)
            await call.answer()
            return

        await repo.update_user_city(str(call.from_user.id), city, area_id)
        new_history = _update_city_history(history, city, area_id)
        await repo.update_preferences(str(call.from_user.id), city_history=new_history)

    await send_city_menu(call, lang, edit=True)


@router.message(EditProfile.city)
async def save_city(message: types.Message, state: FSMContext):
    city_input = (message.text or "").strip()
    user_id = str(message.from_user.id)
    lang = await resolve_lang(user_id, message.from_user.language_code if message.from_user else None)

    if not city_input:
        await message.answer(t("profile.edit_city_empty", lang))
        return

    if city_input.lower() in {"clear", "удалить", "сбросить", "none", "null"}:
        async with db_session() as session:
            repo = UserRepository(session)
            await repo.update_user_city(user_id, None, None)
        await message.answer(t("profile.edit_city_cleared", lang))
        await state.clear()
        return

    if not hh_service.session:
        await message.answer(t("profile.search_city_service_unavailable", lang))
        return

    lookup_msg = await message.answer(t("profile.edit_city_lookup", lang).format(city=city_input))
    area_id = await hh_service.find_area_by_name(city_input)

    if not area_id:
        await message.answer(t("profile.edit_city_not_found", lang).format(city=city_input))
        return

    async with db_session() as session:
        repo = UserRepository(session)
        user = await repo.get_user_by_tg_id(user_id)
        prefs = user.preferences or {} if user else {}
        history = prefs.get("city_history") or []
        new_history = _update_city_history(history, city_input, area_id)

        await repo.update_user_city(user_id, city_input, area_id)
        await repo.update_preferences(user_id, city_history=new_history)

    state_data = await state.get_data()
    menu_chat_id = state_data.get("city_menu_chat_id")
    menu_message_id = state_data.get("city_menu_message_id")
    prompt_message_id = state_data.get("city_prompt_message_id")

    await send_city_menu(
        message,
        lang,
        edit=True,
        chat_id=menu_chat_id or message.chat.id,
        message_id=menu_message_id,
    )
    success_msg = await message.answer(t("profile.edit_city_updated", lang).format(city=city_input))

    async def _safe_delete(msg: types.Message):
        try:
            await msg.delete()
        except Exception as e:
            logger.debug(f"Failed to delete helper message during city update: {e}")

    await _safe_delete(message)
    await _safe_delete(lookup_msg)
    if prompt_message_id:
        try:
            await message.bot.delete_message(chat_id=menu_chat_id or message.chat.id, message_id=prompt_message_id)
        except Exception as e:
            logger.debug(f"Failed to delete city prompt message: {e}")
    await _safe_delete(success_msg)
    await state.clear()
