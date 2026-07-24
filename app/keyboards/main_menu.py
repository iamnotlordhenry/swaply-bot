from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Смотреть предложения")],
            [
                KeyboardButton(text="🤝 Мои мэтчи"),
                KeyboardButton(text="👤 Мой профиль"),
            ],
            [KeyboardButton(text="⚙️ Настройки поиска")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выбери раздел",
    )
