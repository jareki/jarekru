# jarekru

Проект для работы с личной фотоколлекцией: обработка и сортировка фотографий по месяцам + веб-слайдшоу «фото месяца».

### Структура

```
image-editor/
  process.py       — скрипт обработки фото
  config.json      — настройки обработки
  requirements.txt — зависимости (Pillow)
web/
  server.py       — веб-сервер (FastAPI)
  config.json     — настройки веб-сервера
  requirements.txt
  static/
    index.html    — фронтенд слайдшоу
data/
  input/          — сюда кладутся исходные фотографии
  01/ .. 12/      — обработанные фото, по месяцу съёмки
```

---

## image-editor

Скрипт обрабатывает JPG-фотографии: читает дату съёмки из EXIF, раскладывает по папкам `01`–`12` (по месяцам), уменьшает до заданного размера по длинной стороне, удаляет EXIF-данные и переименовывает в случайный UUID.

### Настройки (config.json)

| Параметр    | Описание                              | По умолчанию |
|-------------|---------------------------------------|--------------|
| `data_path` | Путь к папке `data` относительно скрипта | `../data`  |
| `max_size`  | Макс. размер по длинной стороне, px   | `1025`       |
| `quality`   | Качество JPEG при сохранении, %       | `85`         |

### Установка и запуск (Linux)

```bash
# Клонирование
git clone <repo-url>
cd jarekru

# Виртуальное окружение и зависимости
python3 -m venv venv
source venv/bin/activate
pip install -r image-editor/requirements.txt

# Создание входной папки
mkdir -p data/input

# Поместить фотографии в data/input/ и запустить
python image-editor/process.py
```

### Автозапуск через cron

Для периодической обработки новых файлов в `data/input/` добавьте задачу в crontab:

```bash
crontab -e
```

Добавить строку (запуск каждые 5 минут):

```
*/5 * * * * cd /path/to/jarekru && venv/bin/python image-editor/process.py >> /var/log/image-editor.log 2>&1
```

Замените `/path/to/jarekru` на реальный путь к проекту. Интервал `*/5` можно изменить — например, `*/1` для проверки каждую минуту или `0 * * * *` для запуска раз в час.

#### Ротация логов image-editor

Создать `/etc/logrotate.d/image-editor`:

```
/var/log/image-editor.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```

Лог ротируется ежедневно, хранятся 7 архивов (неделя), старые удаляются автоматически.

---

## web — Photo of the Month

Веб-приложение, которое показывает случайное фото текущего месяца на весь экран. Фото автоматически сменяется с плавным crossfade-переходом.

### Настройки (web/config.json)

| Параметр           | Описание                                  | По умолчанию |
|--------------------|-------------------------------------------|--------------|
| `data_path`        | Путь к папке `data` относительно `web/`   | `../data`    |
| `host`             | Адрес для привязки сервера                | `0.0.0.0`    |
| `port`             | Порт сервера                              | `8000`       |
| `interval_seconds` | Интервал смены фото, секунды              | `5`          |

### Дедупликация фото (time-slot)

Чтобы за короткий период все клиенты получали одно и то же фото, выбор привязан к временному слоту. Текущее время в секундах делится нацело на `interval_seconds` — это даёт номер слота. Слот используется как seed для `random.Random`, поэтому в пределах одного интервала `random.choice` всегда возвращает одно и то же фото. При смене слота seed меняется — выбирается другое фото.

### Rate limiting

Эндпоинт `/api/photo` защищён от частых запросов через [slowapi](https://github.com/laurentS/slowapi). Лимит вычисляется автоматически из `interval_seconds`: разрешается вдвое больше запросов в минуту, чем нужно слайдшоу (минимум 2/мин). При `interval_seconds: 5` лимит — 24 запроса в минуту. При превышении клиент получает `429 Too Many Requests`.

### Установка и запуск

```bash
cd web
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

Открыть `http://localhost:8000`. Если в папке `data/{текущий_месяц}/` нет фотографий, отобразится сообщение «No photos for this month».

### Развёртывание на сервере (Caddy + автоматический HTTPS)

Подразумевается Ubuntu/Debian сервер с доменом, направленным на его IP (A-запись в DNS). Caddy автоматически получает и продлевает сертификаты Let's Encrypt.

#### 1. Установка зависимостей

```bash
sudo apt update
sudo apt install -y python3 python3-pip

# Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

# Директория для логов Caddy
sudo mkdir -p /var/log/caddy
sudo chown -R caddy:caddy /var/log/caddy
```

#### 2. Клонирование и настройка проекта

```bash
cd /opt
sudo git clone <repo-url> jarekru

# Сервисный пользователь (без домашней директории, без логина)
sudo useradd -r -s /usr/sbin/nologin photoweb
sudo chown -R photoweb:photoweb /opt/jarekru
sudo chmod -R g+rX /opt/jarekru

# Caddy → группа photoweb (для раздачи фото напрямую)
sudo usermod -aG photoweb caddy

# Виртуальное окружение
cd /opt/jarekru/web
sudo -u photoweb python3 -m venv /opt/jarekru/venv
sudo -u photoweb /opt/jarekru/venv/bin/pip install -r requirements.txt
```

Положить фотографии в `data/{01..12}/` (или загрузить в `data/input/` и обработать через `image-editor/process.py`).

#### 3. Systemd-сервис

Создать `/etc/systemd/system/photo-web.service`:

```ini
[Unit]
Description=Photo of the Month
After=network.target

[Service]
User=photoweb
Group=photoweb
WorkingDirectory=/opt/jarekru/web
ExecStart=/opt/jarekru/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now photo-web
```

#### 4. Caddy — reverse proxy

Заменить содержимое `/etc/caddy/Caddyfile`:

```
photo.example.com {
    log {
        output file /var/log/caddy/access.log {
            roll_size 10mb
            roll_keep 5
            roll_keep_for 168h
        }
        format json
    }

    # Заголовки безопасности
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Content-Security-Policy "default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
        -Server
    }

    # Фото отдаёт Caddy напрямую (zero-copy, без Python)
    handle /photos/* {
        uri strip_prefix /photos
        @badpath not path_regexp ^/\d{2}/[a-f0-9\-]+(_[HV])?\.(jpg|jpeg|png|webp)$
        respond @badpath 404

        root * /opt/jarekru/data
        @goodpath path_regexp ^/\d{2}/[a-f0-9\-]+(_[HV])?\.(jpg|jpeg|png|webp)$
        header @goodpath Cache-Control "public, max-age=86400, immutable"
        file_server {
            index ""
        }
    }

    # API и статика — через uvicorn
    reverse_proxy 127.0.0.1:8000
}
```

- `roll_size 10mb` — ротация при достижении 10 МБ
- `roll_keep 5` — хранить 5 архивов
- `roll_keep_for 168h` — удалять архивы старше 7 дней

Заменить `photo.example.com` на свой домен. Перезапустить:

```bash
sudo systemctl reload caddy
```

Caddy автоматически получит сертификат Let's Encrypt и настроит редирект HTTP → HTTPS. Продление сертификатов — тоже автоматическое, без дополнительной настройки.

#### 5. Firewall (ufw)

Закрываем прямой доступ к порту 8000 — только Caddy должен проксировать запросы:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Порт 8000 не открыт → uvicorn доступен только через Caddy.

#### 6. Перезапуск после обновления файлов

| Что изменилось | Нужен перезапуск | Команда |
|---|---|---|
| `web/server.py` | photo-web | `sudo systemctl restart photo-web` |
| `web/config.json` | photo-web | `sudo systemctl restart photo-web` |
| `web/requirements.txt` | photo-web (после `pip install -r`) | `sudo systemctl restart photo-web` |
| `web/static/*` (HTML, CSS, JS) | нет | отдаются с диска при каждом запросе |
| `data/01..12/*` (фотографии) | нет | подхватываются автоматически |
| `/etc/caddy/Caddyfile` | caddy | `sudo systemctl reload caddy` |
| `image-editor/*` | нет | запускается вручную или по cron |

#### 7. Проверка

```bash
sudo systemctl status photo-web    # uvicorn работает
sudo systemctl status caddy         # caddy работает
curl -I https://photo.example.com   # 200 OK, HTTPS
```

Сайт доступен по `https://photo.example.com`.

#### 8. Защита от ботов — fail2ban

Боты массово сканируют серверы в поисках уязвимостей (`/wp-admin`, `/.env`, `/phpmyadmin` и т.д.). fail2ban анализирует логи Caddy и банит IP-адреса, которые генерируют подозрительные запросы.

##### Установка

```bash
sudo apt install -y fail2ban
```

##### Access-лог Caddy

fail2ban работает с access-логом Caddy, настроенным в шаге 4. Убедитесь, что лог включён в Caddyfile (`log { output file /var/log/caddy/access.log ... }`).

##### Фильтр — `/etc/fail2ban/filter.d/caddy-botscan.conf`

Фильтр срабатывает на 4xx-ответы в JSON-логах Caddy (сканеры запрашивают несуществующие пути и получают 404/403):

```ini
[Definition]
failregex = "client_ip":"<HOST>".*"status":\s*4\d\d
ignoreregex =
```

##### Jail — `/etc/fail2ban/jail.d/caddy-botscan.conf`

```ini
[caddy-botscan]
enabled  = true
port     = http,https
filter   = caddy-botscan
logpath  = /var/log/caddy/access.log
maxretry = 10
findtime = 60
bantime  = 3600
action   = iptables-multiport[name=caddy-botscan, port="http,https", protocol=tcp]
```

- `maxretry = 10` — бан после 10 ошибок 4xx
- `findtime = 60` — за 60 секунд
- `bantime = 3600` — бан на 1 час

Значения можно подстроить под свои потребности. Для более агрессивной защиты уменьшите `maxretry` или увеличьте `bantime`.

##### Ротация логов fail2ban

fail2ban поставляется с конфигом logrotate (`/etc/logrotate.d/fail2ban`). Убедитесь, что он существует и содержит:

```
/var/log/fail2ban.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        fail2ban-client flushlogs 1>/dev/null || true
    endscript
}
```

Если файл отсутствует — создайте его. Логи ротируются ежедневно, хранятся 7 архивов (неделя).

##### Запуск

```bash
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban
```

##### Проверка

```bash
# Статус jail
sudo fail2ban-client status caddy-botscan

# Список забаненных IP
sudo fail2ban-client get caddy-botscan banned

# Ручной разбан IP
sudo fail2ban-client set caddy-botscan unbanip 1.2.3.4
```
