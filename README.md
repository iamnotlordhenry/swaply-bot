# Swaply Bot

Новая версия Telegram-бота Swaply.

## Что уже работает

- запуск Telegram-бота через aiogram;
- подключение к PostgreSQL;
- автоматическое создание таблицы пользователей;
- команда `/start`;
- сохранение пользователя;
- главное меню;
- запуск в Railway.

## Переменные Railway

В разделе Variables должны быть:

- `BOT_TOKEN` — токен Telegram-бота;
- `DATABASE_URL` — адрес PostgreSQL.

Если PostgreSQL добавлен в Railway как отдельный сервис, Railway обычно предоставляет `DATABASE_URL` автоматически.

## Локальный запуск

```bash
python -m venv .venv
pip install -r requirements.txt
python main.py
```

Для локального запуска создай `.env` по образцу `.env.example`.
Сам файл `.env` нельзя загружать в GitHub.


