import json
import math
import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "config.json") as f:
    config = json.load(f)

DATA_DIR = (BASE_DIR / config["data_path"]).resolve()

interval = config.get("interval_seconds", 5)
# Разрешаем чуть больше запросов, чем нужно слайдшоу (x2), но не менее 2/мин
rate_per_minute = max(2, math.ceil(60 / interval * 2))
PHOTO_RATE_LIMIT = f"{rate_per_minute}/minute"

def get_real_ip(request: Request) -> str:
    """Получаем реальный IP клиента из X-Forwarded-For (Caddy) или напрямую."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_photo_cache: dict[int, list[str]] = {}


def get_photos(month_dir: Path, slot: int) -> list[str]:
    """Кэшируем список фото на время одного слота (избегаем iterdir на каждый запрос)."""
    if slot not in _photo_cache:
        _photo_cache.clear()
        _photo_cache[slot] = sorted(
            p.name for p in month_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
    return _photo_cache[slot]


limiter = Limiter(key_func=get_real_ip)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/api/photo")
@limiter.limit(PHOTO_RATE_LIMIT)
def random_photo(request: Request):
    month = datetime.now().strftime("%m")
    month_dir = DATA_DIR / month
    if not month_dir.is_dir():
        raise HTTPException(404, f"No folder for month {month}")

    # Все клиенты в пределах одного time-slot получают одно и то же фото
    slot = int(datetime.now().timestamp()) // interval
    photos = get_photos(month_dir, slot)
    if not photos:
        raise HTTPException(404, "No photos for this month")
    rng = random.Random(slot)
    name = rng.choice(photos)
    return {"url": f"/photos/{month}/{name}"}


@app.get("/api/config")
def get_config():
    return {"interval_seconds": config.get("interval_seconds", 5)}


INDEX_HTML = (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/")
def index():
    return HTMLResponse(INDEX_HTML)


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
