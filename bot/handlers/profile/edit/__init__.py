from aiogram import Router

from bot.handlers.profile.edit import (
    cancel,
    city,
    contacts,
    llm,
    name,
    position,
    resume,
    skills,
)

router = Router()
router.include_router(cancel.router)
router.include_router(city.router)
router.include_router(position.router)
router.include_router(name.router)
router.include_router(contacts.router)
router.include_router(skills.router)
router.include_router(resume.router)
router.include_router(llm.router)
