"""Handlers module"""

from bot.handlers.echo import register_echo_handlers
from bot.handlers.help import register_help_handlers
from bot.handlers.location import register_location_handlers
from bot.handlers.profile import register_profile_handlers
from bot.handlers.search import register_search_handlers
from bot.handlers.start import register_start_handlers

__all__ = [
    "register_start_handlers",
    "register_help_handlers",
    "register_search_handlers",
    "register_location_handlers",
    "register_profile_handlers",
    "register_echo_handlers",
]


def register_all_handlers(router_instance):
    """Register all handlers"""
    register_start_handlers(router_instance)
    register_help_handlers(router_instance)
    register_search_handlers(router_instance)
    register_location_handlers(router_instance)
    register_profile_handlers(router_instance)
    # echo_ at the end
    register_echo_handlers(router_instance)
