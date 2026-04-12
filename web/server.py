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
square_tolerance = config.get("square_tolerance", 0.1)
# Разрешаем чуть больше запросов, чем нужно слайдшоу (x2), но не менее 2/мин
rate_per_minute = max(2, math.ceil(60 / interval * 2))
PHOTO_RATE_LIMIT = f"{rate_per_minute}/minute"


def pick_bucket(ar: float | None) -> str:
    """H — только горизонтальные, V — только вертикальные, both — все."""
    if ar is None:
        return "both"
    if ar > 1 + square_tolerance:
        return "H"
    if ar < 1 - square_tolerance:
        return "V"
    return "both"


def matches_bucket(name: str, bucket: str) -> bool:
    if bucket == "both":
        return True
    stem = name.rsplit(".", 1)[0]
    return stem.endswith(f"_{bucket}")

def get_real_ip(request: Request) -> str:
    """Получаем реальный IP клиента из X-Forwarded-For (Caddy) или напрямую."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_photo_cache: dict[tuple[int, str], list[str]] = {}


def get_photos(month_dir: Path, slot: int, bucket: str) -> list[str]:
    """Кэшируем список фото на время одного слота (избегаем iterdir на каждый запрос)."""
    key = (slot, bucket)
    if key not in _photo_cache:
        # Очищаем кэш при смене слота
        if _photo_cache and next(iter(_photo_cache))[0] != slot:
            _photo_cache.clear()
        all_photos = sorted(
            p.name for p in month_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
        _photo_cache[key] = [n for n in all_photos if matches_bucket(n, bucket)]
    return _photo_cache[key]


limiter = Limiter(key_func=get_real_ip)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/api/photo")
@limiter.limit(PHOTO_RATE_LIMIT)
def random_photo(request: Request, ar: float | None = None):
    month = datetime.now().strftime("%m")
    month_dir = DATA_DIR / month
    if not month_dir.is_dir():
        raise HTTPException(404, f"No folder for month {month}")

    bucket = pick_bucket(ar)
    # Все клиенты в пределах одного time-slot и bucket'а получают одно и то же фото
    slot = int(datetime.now().timestamp()) // interval
    photos = get_photos(month_dir, slot, bucket)
    if not photos:
        raise HTTPException(404, "No photos for this month")
    rng = random.Random((slot, bucket))
    name = rng.choice(photos)
    return {"url": f"/photos/{month}/{name}"}


@app.get("/api/config")
def get_config():
    return {"interval_seconds": config.get("interval_seconds", 5)}


INDEX_PATH = BASE_DIR / "static" / "index.html"
STYLE_PATH = BASE_DIR / "static" / "style.css"


@app.get("/")
def index():
    html = INDEX_PATH.read_text(encoding="utf-8")
    style_mtime = int(STYLE_PATH.stat().st_mtime)
    html = html.replace("/static/style.css", f"/static/style.css?v={style_mtime}")
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
