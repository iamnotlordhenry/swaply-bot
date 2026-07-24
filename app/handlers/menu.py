from aiogram import F, Router
from aiogram.types import Message

router = Router()


@router.message(F.text == "👤 Мой профиль")
async def profile(message: Message) -> None:
    await message.answer(
        "Твой профиль пока в статусе черновика. "
        "Создание профиля добавим следующим шагом."
    )


@router.message(F.text == "🔍 Смотреть предложения")
async def feed(message: Message) -> None:
    await message.answer(
        "Лента появится после создания профилей и настроек поиска."
    )


@router.message(F.text == "🤝 Мои мэтчи")
async def matches(message: Message) -> None:
    await message.answer("У тебя пока нет мэтчей.")


@router.message(F.text == "⚙️ Настройки поиска")
async def search_settings(message: Message) -> None:
    await message.answer(
        "Настройки поиска добавим после создания профиля."
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Пожалуйста, выбери один из пунктов меню.")
