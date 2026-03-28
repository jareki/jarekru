# jarekru

## image-editor

Скрипт `image-editor/process.py` берёт JPG из `data/input/`, раскладывает по `data/01..12/` (месяц из EXIF `DateTimeOriginal`), ресайзит, удаляет EXIF, переименовывает в UUID. Настройки — `image-editor/config.json` (`data_path`, `max_size`, `quality`). Зависимость: Pillow.
