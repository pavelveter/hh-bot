from aiogram import Router

router = Router(name="preferences")

# Register handlers
from . import language, schedule, view  # noqa: E402,F401

__all__ = ["router"]
