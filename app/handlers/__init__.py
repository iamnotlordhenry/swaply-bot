from aiogram import Router

from app.handlers.start import router as start_router
from app.handlers.menu import router as menu_router


def get_main_router() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(menu_router)
    return router
