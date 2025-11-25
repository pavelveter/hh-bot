"""Handler for /location command"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import UserRepository
from bot.db.database import get_db_session
from bot.services.hh_service import hh_service
from bot.utils.i18n import detect_lang, t
from bot.utils.logging import get_logger

logger = get_logger(__name__)

router = Router()


def register_location_handlers(router_instance: Router):
    """Register location command handlers"""
    try:
        router_instance.include_router(router)
        logger.info("Location handlers registered successfully")
    except Exception as e:
        logger.error(f"Failed to register location handlers: {e}")


@router.message(Command("location"))
async def location_handler(message: Message):
    """Handler for the /location command to set user's city"""
    user_id = str(message.from_user.id)
    username = message.from_user.username or "N/A"
    lang = detect_lang(message.from_user.language_code if message.from_user else None)

    # Extract city name from message
    parts = message.text.split(maxsplit=1)
    city_name = parts[1] if len(parts) > 1 else None

    logger.info(f"Location command received from user {user_id} (@{username}) with city: '{city_name}'")

    db_session = await get_db_session()
    if not db_session:
        await message.answer(t("location.db_unavailable", lang))
        return

    try:
        user_repo = UserRepository(db_session)
        user = await user_repo.get_user_by_tg_id(user_id)
        if user and user.language_code:
            lang = detect_lang(user.language_code)

        # If no city provided, show current city or help
        if not city_name:
            city_info = await user_repo.get_user_city(user_id)
            if city_info and city_info[0]:
                await message.answer(
                    t(
                        "location.current_city",
                        lang,
                        city=city_info[0],
                    ),
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    t("location.not_set", lang),
                    parse_mode="HTML",
                )
            return

        # Handle clear command
        if city_name.lower() in ["clear", "удалить", "сбросить", "none", "null"]:
            success = await user_repo.update_user_city(user_id, None, None)
            if success:
                await message.answer(t("location.cleared", lang))
            else:
                await message.answer(t("location.clear_failed", lang))
            return

        # Check if HH service is available
        if not hh_service.session:
            await message.answer(t("search.service_unavailable", lang))
            return

        # Find area ID for the city
        await message.answer(t("location.searching", lang).format(city=city_name))
        area_id = await hh_service.find_area_by_name(city_name)

        if not area_id:
            await message.answer(t("location.not_found", lang).format(city=city_name))
            return

        # Update user's city
        success = await user_repo.update_user_city(user_id, city_name, area_id)
        if success:
            await message.answer(
                t("location.set", lang).format(city=city_name),
                parse_mode="HTML",
            )
            logger.success(f"User {user_id} set location to {city_name} (area_id: {area_id})")
        else:
            await message.answer(t("location.set_failed", lang))

    except Exception as e:
        logger.error(f"Failed to handle location command for user {user_id}: {e}")
        await message.answer(t("location.error_processing", lang))
    finally:
        await db_session.close()
