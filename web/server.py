import json
import math
import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "config.json") as f:
    config = json.load(f)

DATA_DIR = (BASE_DIR / config["data_path"]).resolve()

interval = config.get("interval_seconds", 5)
# Разрешаем чуть больше запросов, чем нужно слайдшоу (x2), но не менее 2/мин
rate_per_minute = max(2, math.ceil(60 / interval * 2))
PHOTO_RATE_LIMIT = f"{rate_per_minute}/minute"

limiter = Limiter(key_func=get_remote_address)
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

    photos = [p.name for p in month_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not photos:
        raise HTTPException(404, f"No photos for month {month}")

    # Все клиенты в пределах одного time-slot получают одно и то же фото
    slot = int(datetime.now().timestamp()) // interval
    rng = random.Random(slot)
    name = rng.choice(photos)
    return {"url": f"/photos/{month}/{name}"}


@app.get("/photos/{month}/{filename}")
def serve_photo(month: str, filename: str):
    path = (DATA_DIR / month / filename).resolve()
    if not path.is_file() or not str(path).startswith(str(DATA_DIR)):
        raise HTTPException(404)
    return FileResponse(path)


@app.get("/api/config")
def get_config():
    return {"interval_seconds": config.get("interval_seconds", 5)}


@app.get("/")
def index():
    return HTMLResponse((BASE_DIR / "static" / "index.html").read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
