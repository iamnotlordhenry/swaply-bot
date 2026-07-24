import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from dotenv import load_dotenv


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", "swaply.sqlite3").strip()

logging.basicConfig(level=logging.INFO)
router = Router()


CATALOG = {
    "service": [
        "Тату", "Маникюр", "Фотограф", "Дизайнер", "Программист",
        "Массаж", "Ремонт", "Копирайтер", "Визажист", "Репетитор",
    ],
    "product": [
        "Одежда", "Обувь", "Мебель", "Книги", "Техника",
        "Украшения", "Косметика", "Игрушки", "Картины", "Растения",
    ],
    "advertising": [
        "Реклама в Telegram", "Реклама во ВКонтакте",
        "Реклама в Instagram", "Реклама на сайте", "Реклама у блогера",
    ],
}

TYPE_LABELS = {
    "service": "🛠 Услуга",
    "product": "📦 Товар",
    "advertising": "📣 Реклама",
}

EXPERIENCE_LABELS = {
    "less_1": "До 1 года",
    "1_3": "1–3 года",
    "3_5": "3–5 лет",
    "more_5": "Более 5 лет",
    "skip": "Не указано",
}


class Registration(StatesGroup):
    name = State()
    cities = State()
    can_list = State()
    can_type = State()
    can_search = State()
    can_city_select = State()
    can_description = State()
    can_experience = State()
    can_link = State()
    want_list = State()
    want_type = State()
    want_search = State()
    want_city_select = State()
    want_description = State()
    about = State()
    photos = State()
    preview = State()


@dataclass
class DraftItem:
    direction: str
    item_type: str
    title: str
    cities: list[str]
    any_city: bool = False
    description: str = ""
    experience: str = ""
    link: str = ""


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT NOT NULL,
                cities_json TEXT NOT NULL,
                about TEXT,
                active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('can', 'want')),
                item_type TEXT NOT NULL,
                title TEXT NOT NULL,
                cities_json TEXT NOT NULL,
                any_city INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                experience TEXT,
                link TEXT,
                FOREIGN KEY(user_id) REFERENCES profiles(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY(user_id) REFERENCES profiles(user_id) ON DELETE CASCADE
            );
            """
        )
        await db.commit()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_loads(value: str) -> Any:
    return json.loads(value)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Моя анкета")],
            [KeyboardButton(text="✏️ Заполнить заново")],
        ],
        resize_keyboard=True,
    )


def continue_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить", callback_data="list:add")],
            [InlineKeyboardButton(text="➡️ Продолжить", callback_data="list:continue")],
        ]
    )


def item_type_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"{prefix}:type:{key}")]
            for key, label in TYPE_LABELS.items()
        ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}:back")]]
    )


def catalog_keyboard(prefix: str, item_type: str, query: str) -> InlineKeyboardMarkup:
    query_l = query.lower().strip()
    matches = [x for x in CATALOG[item_type] if query_l in x.lower()][:8]
    rows = [
        [InlineKeyboardButton(text=f"✅ {title}", callback_data=f"{prefix}:catalog:{title}")]
        for title in matches
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}:catalog_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def city_keyboard(cities: list[str], selected: list[str], any_city: bool, prefix: str) -> InlineKeyboardMarkup:
    rows = []
    for index, city in enumerate(cities):
        checked = city in selected and not any_city
        rows.append([
            InlineKeyboardButton(
                text=f"{'☑' if checked else '☐'} {city}",
                callback_data=f"{prefix}:city:{index}",
            )
        ])
    rows.extend([
        [InlineKeyboardButton(
            text=f"{'☑' if any_city else '🌍'} Любой город",
            callback_data=f"{prefix}:any_city",
        )],
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"{prefix}:city_done")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}:city_back")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def experience_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"exp:{key}")]
            for key, label in EXPERIENCE_LABELS.items()
        ]
    )


def skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data=callback_data)]]
    )


def preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Опубликовать", callback_data="preview:publish")],
            [InlineKeyboardButton(text="🔄 Заполнить заново", callback_data="preview:restart")],
        ]
    )


async def get_data_list(state: FSMContext, key: str) -> list[dict]:
    data = await state.get_data()
    return data.get(key, [])


def render_items(items: list[dict], heading: str) -> str:
    lines = [heading]
    if not items:
        lines.append("\nПока ничего не добавлено.")
        return "\n".join(lines)

    for item in items:
        geo = "Любой город" if item.get("any_city") else ", ".join(item.get("cities", []))
        lines.append(f"\n• <b>{item['title']}</b>")
        lines.append(f"  {TYPE_LABELS[item['item_type']]}")
        lines.append(f"  📍 {geo}")
        if item.get("experience") and item["experience"] != "skip":
            lines.append(f"  🕒 {EXPERIENCE_LABELS[item['experience']]}")
        if item.get("description"):
            lines.append(f"  📝 {item['description']}")
        if item.get("link"):
            lines.append(f"  🔗 {item['link']}")
    return "\n".join(lines)


async def show_can_list(target: Message | CallbackQuery, state: FSMContext) -> None:
    items = await get_data_list(state, "can_items")
    text = render_items(items, "💼 <b>Что я могу</b>")
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=continue_keyboard())
        await target.answer()
    else:
        await target.answer(text, reply_markup=continue_keyboard())
    await state.set_state(Registration.can_list)


async def show_want_list(target: Message | CallbackQuery, state: FSMContext) -> None:
    items = await get_data_list(state, "want_items")
    text = render_items(items, "❤️ <b>Что я хочу</b>")
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=continue_keyboard())
        await target.answer()
    else:
        await target.answer(text, reply_markup=continue_keyboard())
    await state.set_state(Registration.want_list)


async def start_registration(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Registration.name)
    await message.answer(
        "Добро пожаловать в <b>Swaply</b> 👋\n\nКак вас зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def command_start(message: Message, state: FSMContext) -> None:
    await start_registration(message, state)


@router.message(Command("cancel"))
async def command_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Заполнение отменено.", reply_markup=main_menu())


@router.message(F.text == "✏️ Заполнить заново")
async def restart_from_menu(message: Message, state: FSMContext) -> None:
    await start_registration(message, state)


@router.message(Registration.name)
async def receive_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not 2 <= len(name) <= 40:
        await message.answer("Введите имя длиной от 2 до 40 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(Registration.cities)
    await message.answer(
        "🏙 <b>В каких городах вы готовы обмениваться?</b>\n\n"
        "Введите до 3 городов через запятую.\n"
        "Например: Санкт-Петербург, Курган"
    )


@router.message(Registration.cities)
async def receive_cities(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    cities = []
    for part in raw.split(","):
        city = part.strip()
        if city and city.casefold() not in [x.casefold() for x in cities]:
            cities.append(city)
    if not cities or len(cities) > 3:
        await message.answer("Нужно указать от 1 до 3 городов через запятую.")
        return
    await state.update_data(cities=cities, can_items=[], want_items=[], photos=[])
    await show_can_list(message, state)


@router.callback_query(Registration.can_list, F.data == "list:add")
async def can_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.can_type)
    await callback.message.edit_text(
        "Что вы можете предложить?",
        reply_markup=item_type_keyboard("can"),
    )
    await callback.answer()


@router.callback_query(Registration.can_list, F.data == "list:continue")
async def can_continue(callback: CallbackQuery, state: FSMContext) -> None:
    await show_want_list(callback, state)


@router.callback_query(Registration.can_type, F.data.startswith("can:type:"))
async def can_type(callback: CallbackQuery, state: FSMContext) -> None:
    item_type = callback.data.rsplit(":", 1)[1]
    await state.update_data(draft={"direction": "can", "item_type": item_type})
    await state.set_state(Registration.can_search)
    await callback.message.edit_text(
        f"{TYPE_LABELS[item_type]}\n\n🔎 Введите, что вы предлагаете.\n"
        "Например: тату, фотограф, мебель"
    )
    await callback.answer()


@router.callback_query(Registration.can_type, F.data == "can:back")
async def can_type_back(callback: CallbackQuery, state: FSMContext) -> None:
    await show_can_list(callback, state)


@router.message(Registration.can_search)
async def can_search(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data["draft"]
    query = (message.text or "").strip()
    kb = catalog_keyboard("can", draft["item_type"], query)
    if len(kb.inline_keyboard) == 1:
        await message.answer("Ничего не найдено. Попробуйте более общее название.")
        return
    await message.answer("Выберите подходящий вариант:", reply_markup=kb)


@router.callback_query(Registration.can_search, F.data.startswith("can:catalog:"))
async def can_catalog_select(callback: CallbackQuery, state: FSMContext) -> None:
    title = callback.data.split(":", 2)[2]
    data = await state.get_data()
    draft = data["draft"]
    draft.update({"title": title, "selected_cities": [], "any_city": False})
    await state.update_data(draft=draft)
    await state.set_state(Registration.can_city_select)
    await callback.message.edit_text(
        "📍 <b>Где доступно это предложение?</b>",
        reply_markup=city_keyboard(data["cities"], [], False, "can"),
    )
    await callback.answer()


@router.callback_query(Registration.can_search, F.data == "can:catalog_back")
async def can_catalog_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.can_type)
    await callback.message.edit_text(
        "Что вы можете предложить?",
        reply_markup=item_type_keyboard("can"),
    )
    await callback.answer()


@router.callback_query(Registration.can_city_select, F.data.startswith("can:city:"))
async def can_city_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.rsplit(":", 1)[1])
    data = await state.get_data()
    draft = data["draft"]
    city = data["cities"][index]
    selected = draft.get("selected_cities", [])
    if city in selected:
        selected.remove(city)
    else:
        selected.append(city)
    draft["selected_cities"] = selected
    draft["any_city"] = False
    await state.update_data(draft=draft)
    await callback.message.edit_reply_markup(
        reply_markup=city_keyboard(data["cities"], selected, False, "can")
    )
    await callback.answer()


@router.callback_query(Registration.can_city_select, F.data == "can:any_city")
async def can_any_city(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data["draft"]
    draft["any_city"] = not draft.get("any_city", False)
    if draft["any_city"]:
        draft["selected_cities"] = []
    await state.update_data(draft=draft)
    await callback.message.edit_reply_markup(
        reply_markup=city_keyboard(
            data["cities"], draft.get("selected_cities", []), draft["any_city"], "can"
        )
    )
    await callback.answer()


@router.callback_query(Registration.can_city_select, F.data == "can:city_done")
async def can_city_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data["draft"]
    if not draft.get("any_city") and not draft.get("selected_cities"):
        await callback.answer("Выберите хотя бы один город.", show_alert=True)
        return
    await state.set_state(Registration.can_description)
    await callback.message.edit_text(
        "📝 <b>Опишите предложение</b>\n\n"
        "Что именно вы готовы сделать или передать? Что входит в предложение?\n\n"
        "Поле необязательное.",
        reply_markup=skip_keyboard("can:description_skip"),
    )
    await callback.answer()


@router.callback_query(Registration.can_city_select, F.data == "can:city_back")
async def can_city_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.can_search)
    await callback.message.edit_text("🔎 Введите другое название предложения.")
    await callback.answer()


async def after_can_description(target: Message | CallbackQuery, state: FSMContext, description: str) -> None:
    data = await state.get_data()
    draft = data["draft"]
    draft["description"] = description
    await state.update_data(draft=draft)

    if draft["item_type"] == "service":
        await state.set_state(Registration.can_experience)
        text = "🕒 <b>Опыт работы</b>\n\nВыберите подходящий вариант."
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=experience_keyboard())
            await target.answer()
        else:
            await target.answer(text, reply_markup=experience_keyboard())
    else:
        await ask_can_link(target, state)


@router.message(Registration.can_description)
async def can_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 1000:
        await message.answer("Описание слишком длинное. Максимум 1000 символов.")
        return
    await after_can_description(message, state, text)


@router.callback_query(Registration.can_description, F.data == "can:description_skip")
async def can_description_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await after_can_description(callback, state, "")


@router.callback_query(Registration.can_experience, F.data.startswith("exp:"))
async def can_experience(callback: CallbackQuery, state: FSMContext) -> None:
    exp = callback.data.split(":", 1)[1]
    data = await state.get_data()
    draft = data["draft"]
    draft["experience"] = exp
    await state.update_data(draft=draft)
    await ask_can_link(callback, state)


async def ask_can_link(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.can_link)
    text = (
        "🔗 <b>Добавить ссылку для этого предложения?</b>\n\n"
        "Можно указать Instagram, Telegram, VK, Behance, сайт или другое портфолио.\n\n"
        "Отправьте одну ссылку или нажмите «Пропустить»."
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=skip_keyboard("can:link_skip"))
        await target.answer()
    else:
        await target.answer(text, reply_markup=skip_keyboard("can:link_skip"))


async def finish_can_item(target: Message | CallbackQuery, state: FSMContext, link: str) -> None:
    data = await state.get_data()
    draft = data["draft"]
    draft["link"] = link
    item = {
        "direction": "can",
        "item_type": draft["item_type"],
        "title": draft["title"],
        "cities": draft.get("selected_cities", []),
        "any_city": draft.get("any_city", False),
        "description": draft.get("description", ""),
        "experience": draft.get("experience", ""),
        "link": draft.get("link", ""),
    }
    can_items = data.get("can_items", [])
    can_items.append(item)
    await state.update_data(can_items=can_items, draft=None)
    await show_can_list(target, state)


@router.message(Registration.can_link)
async def can_link(message: Message, state: FSMContext) -> None:
    link = (message.text or "").strip()
    if len(link) > 500:
        await message.answer("Ссылка слишком длинная.")
        return
    await finish_can_item(message, state, link)


@router.callback_query(Registration.can_link, F.data == "can:link_skip")
async def can_link_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_can_item(callback, state, "")


@router.callback_query(Registration.want_list, F.data == "list:add")
async def want_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.want_type)
    await callback.message.edit_text(
        "Что вы хотите получить взамен?",
        reply_markup=item_type_keyboard("want"),
    )
    await callback.answer()


@router.callback_query(Registration.want_list, F.data == "list:continue")
async def want_continue(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.about)
    await callback.message.edit_text(
        "📝 <b>Расскажите немного о себе</b>\n\nПоле необязательное.",
        reply_markup=skip_keyboard("about:skip"),
    )
    await callback.answer()


@router.callback_query(Registration.want_type, F.data.startswith("want:type:"))
async def want_type(callback: CallbackQuery, state: FSMContext) -> None:
    item_type = callback.data.rsplit(":", 1)[1]
    await state.update_data(draft={"direction": "want", "item_type": item_type})
    await state.set_state(Registration.want_search)
    await callback.message.edit_text(
        f"{TYPE_LABELS[item_type]}\n\n🔎 Введите, что вы хотите найти."
    )
    await callback.answer()


@router.callback_query(Registration.want_type, F.data == "want:back")
async def want_type_back(callback: CallbackQuery, state: FSMContext) -> None:
    await show_want_list(callback, state)


@router.message(Registration.want_search)
async def want_search(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data["draft"]
    query = (message.text or "").strip()
    kb = catalog_keyboard("want", draft["item_type"], query)
    if len(kb.inline_keyboard) == 1:
        await message.answer("Ничего не найдено. Попробуйте более общее название.")
        return
    await message.answer("Выберите подходящий вариант:", reply_markup=kb)


@router.callback_query(Registration.want_search, F.data.startswith("want:catalog:"))
async def want_catalog_select(callback: CallbackQuery, state: FSMContext) -> None:
    title = callback.data.split(":", 2)[2]
    data = await state.get_data()
    draft = data["draft"]
    draft.update({"title": title, "selected_cities": [], "any_city": False})
    await state.update_data(draft=draft)
    await state.set_state(Registration.want_city_select)
    await callback.message.edit_text(
        "📍 <b>Где вы хотите найти это?</b>",
        reply_markup=city_keyboard(data["cities"], [], False, "want"),
    )
    await callback.answer()


@router.callback_query(Registration.want_search, F.data == "want:catalog_back")
async def want_catalog_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.want_type)
    await callback.message.edit_text(
        "Что вы хотите получить взамен?",
        reply_markup=item_type_keyboard("want"),
    )
    await callback.answer()


@router.callback_query(Registration.want_city_select, F.data.startswith("want:city:"))
async def want_city_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.rsplit(":", 1)[1])
    data = await state.get_data()
    draft = data["draft"]
    city = data["cities"][index]
    selected = draft.get("selected_cities", [])
    if city in selected:
        selected.remove(city)
    else:
        selected.append(city)
    draft["selected_cities"] = selected
    draft["any_city"] = False
    await state.update_data(draft=draft)
    await callback.message.edit_reply_markup(
        reply_markup=city_keyboard(data["cities"], selected, False, "want")
    )
    await callback.answer()


@router.callback_query(Registration.want_city_select, F.data == "want:any_city")
async def want_any_city(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data["draft"]
    draft["any_city"] = not draft.get("any_city", False)
    if draft["any_city"]:
        draft["selected_cities"] = []
    await state.update_data(draft=draft)
    await callback.message.edit_reply_markup(
        reply_markup=city_keyboard(
            data["cities"], draft.get("selected_cities", []), draft["any_city"], "want"
        )
    )
    await callback.answer()


@router.callback_query(Registration.want_city_select, F.data == "want:city_done")
async def want_city_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    draft = data["draft"]
    if not draft.get("any_city") and not draft.get("selected_cities"):
        await callback.answer("Выберите хотя бы один город.", show_alert=True)
        return
    await state.set_state(Registration.want_description)
    await callback.message.edit_text(
        "📝 Добавьте уточнение: что именно вы хотите получить?\n\nПоле необязательное.",
        reply_markup=skip_keyboard("want:description_skip"),
    )
    await callback.answer()


@router.callback_query(Registration.want_city_select, F.data == "want:city_back")
async def want_city_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.want_search)
    await callback.message.edit_text("🔎 Введите другое название.")
    await callback.answer()


async def finish_want_item(target: Message | CallbackQuery, state: FSMContext, description: str) -> None:
    data = await state.get_data()
    draft = data["draft"]
    item = {
        "direction": "want",
        "item_type": draft["item_type"],
        "title": draft["title"],
        "cities": draft.get("selected_cities", []),
        "any_city": draft.get("any_city", False),
        "description": description,
        "experience": "",
        "link": "",
    }
    items = data.get("want_items", [])
    items.append(item)
    await state.update_data(want_items=items, draft=None)
    await show_want_list(target, state)


@router.message(Registration.want_description)
async def want_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 1000:
        await message.answer("Описание слишком длинное. Максимум 1000 символов.")
        return
    await finish_want_item(message, state, text)


@router.callback_query(Registration.want_description, F.data == "want:description_skip")
async def want_description_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_want_item(callback, state, "")


async def ask_photos(target: Message | CallbackQuery, state: FSMContext, about: str) -> None:
    await state.update_data(about=about)
    await state.set_state(Registration.photos)
    text = (
        "📷 <b>Добавьте фотографии</b>\n\n"
        "Добавьте до 10 фотографий ваших услуг, работ, проектов или товаров.\n\n"
        "Отправляйте фотографии по одной. Когда закончите, нажмите «Готово»."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Готово", callback_data="photos:done")],
            [InlineKeyboardButton(text="Пропустить", callback_data="photos:skip")],
        ]
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.message(Registration.about)
async def about(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) > 1000:
        await message.answer("Текст слишком длинный. Максимум 1000 символов.")
        return
    await ask_photos(message, state, text)


@router.callback_query(Registration.about, F.data == "about:skip")
async def about_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await ask_photos(callback, state, "")


@router.message(Registration.photos, F.photo)
async def receive_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 10:
        await message.answer("Уже загружено 10 фотографий — это максимальный лимит.")
        return
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(f"Фото добавлено: {len(photos)} из 10.")


@router.message(Registration.photos)
async def invalid_photo(message: Message) -> None:
    await message.answer("Отправьте фотографию или нажмите кнопку «Готово».")


@router.callback_query(Registration.photos, F.data.in_({"photos:done", "photos:skip"}))
async def photos_done(callback: CallbackQuery, state: FSMContext) -> None:
    await show_preview(callback, state)


async def build_preview(state: FSMContext) -> str:
    data = await state.get_data()
    lines = [
        "🎉 <b>Ваша анкета готова!</b>",
        "",
        f"👤 <b>{data['name']}</b>",
        f"📍 {', '.join(data['cities'])}",
        "",
        render_items(data.get("can_items", []), "💼 <b>Что я могу</b>"),
        "",
        render_items(data.get("want_items", []), "❤️ <b>Что я хочу</b>"),
    ]
    if data.get("about"):
        lines.extend(["", "📝 <b>О себе</b>", data["about"]])
    lines.extend(["", f"📷 Фото: {len(data.get('photos', []))} из 10"])
    return "\n".join(lines)


async def show_preview(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Registration.preview)
    text = await build_preview(state)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=preview_keyboard())
        await target.answer()
    else:
        await target.answer(text, reply_markup=preview_keyboard())


async def save_profile(message_or_callback: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = message_or_callback.from_user
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """
            INSERT INTO profiles(user_id, username, name, cities_json, about, active, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                name=excluded.name,
                cities_json=excluded.cities_json,
                about=excluded.about,
                active=1,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                user.id,
                user.username,
                data["name"],
                json_dumps(data["cities"]),
                data.get("about", ""),
            ),
        )
        await db.execute("DELETE FROM items WHERE user_id = ?", (user.id,))
        await db.execute("DELETE FROM photos WHERE user_id = ?", (user.id,))

        for item in data.get("can_items", []) + data.get("want_items", []):
            await db.execute(
                """
                INSERT INTO items(
                    user_id, direction, item_type, title, cities_json,
                    any_city, description, experience, link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    item["direction"],
                    item["item_type"],
                    item["title"],
                    json_dumps(item.get("cities", [])),
                    int(item.get("any_city", False)),
                    item.get("description", ""),
                    item.get("experience", ""),
                    item.get("link", ""),
                ),
            )

        for position, file_id in enumerate(data.get("photos", []), start=1):
            await db.execute(
                "INSERT INTO photos(user_id, file_id, position) VALUES (?, ?, ?)",
                (user.id, file_id, position),
            )

        await db.commit()


@router.callback_query(Registration.preview, F.data == "preview:publish")
async def publish(callback: CallbackQuery, state: FSMContext) -> None:
    await save_profile(callback, state)
    await state.clear()
    await callback.message.edit_text(
        "🚀 <b>Анкета опубликована!</b>\n\n"
        "Теперь она сохранена в базе Swaply."
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(Registration.preview, F.data == "preview:restart")
async def preview_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Registration.name)
    await callback.message.edit_text("Как вас зовут?")
    await callback.answer()


@router.message(F.text == "👤 Моя анкета")
async def my_profile(message: Message) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        profile = await (
            await db.execute("SELECT * FROM profiles WHERE user_id = ?", (message.from_user.id,))
        ).fetchone()
        if not profile:
            await message.answer("У вас пока нет опубликованной анкеты. Нажмите /start.")
            return

        rows = await (
            await db.execute(
                "SELECT * FROM items WHERE user_id = ? ORDER BY direction, id",
                (message.from_user.id,),
            )
        ).fetchall()
        photos = await (
            await db.execute(
                "SELECT file_id FROM photos WHERE user_id = ? ORDER BY position",
                (message.from_user.id,),
            )
        ).fetchall()

    can_items, want_items = [], []
    for row in rows:
        item = {
            "direction": row["direction"],
            "item_type": row["item_type"],
            "title": row["title"],
            "cities": json_loads(row["cities_json"]),
            "any_city": bool(row["any_city"]),
            "description": row["description"] or "",
            "experience": row["experience"] or "",
            "link": row["link"] or "",
        }
        (can_items if row["direction"] == "can" else want_items).append(item)

    lines = [
        f"👤 <b>{profile['name']}</b>",
        f"📍 {', '.join(json_loads(profile['cities_json']))}",
        "",
        render_items(can_items, "💼 <b>Что я могу</b>"),
        "",
        render_items(want_items, "❤️ <b>Что я хочу</b>"),
    ]
    if profile["about"]:
        lines.extend(["", "📝 <b>О себе</b>", profile["about"]])
    lines.extend(["", f"📷 Фото: {len(photos)} из 10"])
    await message.answer("\n".join(lines), reply_markup=main_menu())


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN не задан. Создайте файл .env по примеру .env.example."
        )

    await init_db()
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
