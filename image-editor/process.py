import json
import uuid
import sys
from pathlib import Path

from PIL import Image, ImageOps, ExifTags

EXIF_DATE_TAG = 36867  # DateTimeOriginal


def load_config(script_dir: Path) -> dict:
    config_path = script_dir / "config.json"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def get_month(image: Image.Image) -> str | None:
    exif = image.getexif()
    if not exif:
        return None
    # DateTimeOriginal may be in IFD block
    ifd = exif.get_ifd(ExifTags.IFD.Exif)
    date_str = ifd.get(EXIF_DATE_TAG) or exif.get(EXIF_DATE_TAG)
    if not date_str:
        return None
    # Format: "YYYY:MM:DD HH:MM:SS"
    try:
        month = date_str.split(":")[1]
        if month.isdigit() and 1 <= int(month) <= 12:
            return month.zfill(2)
    except (IndexError, ValueError):
        pass
    return None


def process_image(src: Path, dest_dir: Path, max_size: int, quality: int) -> bool:
    with Image.open(src) as img:
        month = get_month(img)
        if month is None:
            print(f"  SKIP (no EXIF date): {src.name}")
            return False

        # Prepare output directory
        out_dir = dest_dir / month
        out_dir.mkdir(parents=True, exist_ok=True)

        # Apply EXIF orientation so physical pixels match visual orientation
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed (e.g. RGBA PNGs saved as .jpg)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize keeping aspect ratio (only shrinks, never enlarges)
        img.thumbnail((max_size, max_size), Image.LANCZOS)

        orientation = "_H" if img.width >= img.height else "_V"

        # Save without EXIF
        out_path = out_dir / f"{uuid.uuid4()}{orientation}.jpg"
        img.save(out_path, "JPEG", quality=quality)
        print(f"  OK: {src.name} -> {month}/{out_path.name}")
        return True


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    config = load_config(script_dir)

    data_path = (script_dir / config["data_path"]).resolve()
    max_size = config.get("max_size", 1025)
    quality = config.get("quality", 85)

    input_dir = data_path / config.get("input_path", "input")
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        sys.exit(1)

    files = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg")
    )

    if not files:
        print("No JPG files found in input/")
        return

    print(f"Processing {len(files)} file(s)...")
    for f in files:
        if process_image(f, data_path, max_size, quality):
            f.unlink()

    print("Done.")


if __name__ == "__main__":
    main()
