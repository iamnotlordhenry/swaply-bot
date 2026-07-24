import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import get_settings
from app.database import create_tables
from app.handlers import get_main_router
from app.middlewares.database import DatabaseMiddleware


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    settings = get_settings()
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()

    dispatcher.update.middleware(DatabaseMiddleware())
    dispatcher.include_router(get_main_router())

    await create_tables()

    logging.info("Swaply bot started")
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
