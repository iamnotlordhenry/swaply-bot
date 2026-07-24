from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.main_menu import main_menu_keyboard
from app.models.user import User

router = Router()


@router.message(CommandStart())
async def command_start(message: Message, session: AsyncSession) -> None:
    telegram_user = message.from_user
    if telegram_user is None:
        return

    result = await session.execute(
        select(User).where(User.telegram_id == telegram_user.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )
        session.add(user)
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name

    await session.commit()

    await message.answer(
        "Привет! Я Swaply — помогу найти людей для полезного обмена.\n\n"
        "Сейчас мы запускаем новую версию. Первый шаг — создать профиль.",
        reply_markup=main_menu_keyboard(),
    )
