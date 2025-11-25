from aiogram import Router

from bot.handlers.profile import edit_profile, preferences, search_settings, view

router = Router()


def register_profile_handlers(router_instance: Router):
    router_instance.include_router(view.router)
    router_instance.include_router(edit_profile.router)
    router_instance.include_router(search_settings.router)
    router_instance.include_router(preferences.router)
