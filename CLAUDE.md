# jarekru

Проект состоит из двух независимых компонентов, работающих с общей папкой `data/01..12/`.

## image-editor

Скрипт `image-editor/process.py` берёт JPG из `data/input/`, раскладывает по `data/01..12/` (месяц из EXIF `DateTimeOriginal`), ресайзит, удаляет EXIF, переименовывает в UUID. Настройки — `image-editor/config.json` (`data_path`, `max_size`, `quality`). Зависимость: Pillow.

## web (Photo of the Month)

Веб-приложение на FastAPI, показывает случайное фото текущего месяца в fullscreen-слайдшоу с crossfade-переходом.

- `web/server.py` — бэкенд: `GET /api/photo` (случайное фото текущего месяца), `GET /api/config` (интервал), `GET /photos/{month}/{file}` (раздача файлов из `data/`), `GET /` (index.html).
- `web/static/index.html` — фронтенд: два `<img>` с CSS opacity transition, JS `setInterval` + `fetch`.
- `web/config.json` — настройки: `data_path`, `host`, `port`, `interval_seconds`.
- Зависимости: fastapi, uvicorn, slowapi (`web/requirements.txt`).
- Rate limit на `/api/photo` через slowapi: лимит вычисляется из `interval_seconds` (x2 с запасом, минимум 2/мин). При превышении — 429.
