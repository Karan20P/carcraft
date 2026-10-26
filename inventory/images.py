"""
Stock photos for car models, from Wikimedia Commons (freely licensed).

Photos are downloaded once into MEDIA_ROOT/car_models/<slug>.jpg with a
credits.json alongside, then attached to CarModel rows by name. Re-seeding
re-attaches the files already on disk without downloading again.
"""
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from PIL import Image

# Model name -> Wikipedia article (or an exact "File:..." on Commons).
SOURCES = {
    "Swift": "Suzuki Swift",
    "Baleno": "Suzuki Baleno (2015)",
    "Brezza": "Maruti Suzuki Brezza",
    "i20": "Hyundai i20",
    "Creta": "Hyundai Creta",
    "Verna": "Hyundai Verna",
    "Punch": "Tata Punch",
    "Nexon": "Tata Nexon",
    "Harrier": "Tata Harrier",
    "XUV700": "Mahindra XUV700",
    "Scorpio-N": "Mahindra Scorpio-N",
    "City": "Honda City",
    "Amaze": "Honda Amaze",
    "Innova Crysta": "Toyota Innova",
    "Fortuner": "Toyota Fortuner",
}

API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "CarCraftCollegeProject/1.0 (educational demo; Django)"
WIDTH = 1200


def image_dir():
    path = Path(settings.MEDIA_ROOT) / "car_models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _get_json(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:
                raise
            time.sleep(10 * (attempt + 1))


def _plain(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html or ""))).strip()


def lookup(source):
    """
    Return (thumb_url, info) for an article's lead image or an explicit File: title,
    where info = {"credit", "source", "license_url"} for attribution.
    """
    file_title = source
    if not source.startswith("File:"):
        data = _get_json({"action": "query", "titles": source, "prop": "pageimages", "piprop": "name", "redirects": 1})
        page = data["query"]["pages"][0]
        if "pageimage" not in page:
            raise ValueError(f"No lead image on '{source}'")
        file_title = "File:" + page["pageimage"]

    data = _get_json({
        "action": "query", "titles": file_title, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": WIDTH,
    })
    info = data["query"]["pages"][0]["imageinfo"][0]
    meta = info.get("extmetadata", {})
    artist = _plain(meta.get("Artist", {}).get("value")) or "Unknown author"
    licence = _plain(meta.get("LicenseShortName", {}).get("value")) or "see source"
    credit = f"Photo: {artist} · {licence} · Wikimedia Commons"
    return info.get("thumburl") or info["url"], {
        "credit": credit[:300],
        "source": info.get("descriptionurl", ""),
        "license_url": meta.get("LicenseUrl", {}).get("value", ""),
    }


def _fetch(url, retries=4):
    """GET with polite back-off when Wikimedia rate-limits us (HTTP 429)."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if not resp.headers.get("Content-Type", "").startswith("image/"):
                    raise ValueError("not an image")
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == retries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def _save_web_jpeg(data, target):
    """Validate the download is a real image and store a web-sized JPEG."""
    with Image.open(io.BytesIO(data)) as img:
        img = img.convert("RGB")
        img.thumbnail((WIDTH, WIDTH))
        img.save(target, "JPEG", quality=82, optimize=True, progressive=True)


def download_all(stdout=None, force=False):
    folder = image_dir()
    credits_path = folder / "credits.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.exists() else {}
    for model_name, source in SOURCES.items():
        target = folder / f"{slugify(model_name)}.jpg"
        if target.exists() and isinstance(credits.get(model_name), dict) and not force:
            continue
        try:
            url, info = lookup(source)
            if force or not target.exists():
                _save_web_jpeg(_fetch(url), target)
            credits[model_name] = info
            if stdout:
                stdout.write(f"  OK   {model_name}: {info['credit']}".encode("ascii", "replace").decode())
        except Exception as exc:  # keep going; the silhouette is a fine fallback
            if stdout:
                stdout.write(f"  FAIL {model_name}: {exc}")
        time.sleep(1.5)  # be gentle with Wikimedia
    credits_path.write_text(json.dumps(credits, indent=2, ensure_ascii=False), encoding="utf-8")
    write_credits_md(credits)


def write_credits_md(credits):
    """Attribution file for the repo, as required by the photos' CC licences."""
    lines = [
        "# Photo credits",
        "",
        "Car model photos in `media/car_models/` come from Wikimedia Commons and are resized for the web.",
        "They remain under their original licences (listed below), separate from this project's code.",
        "",
        "| Model | Credit | Source | Licence |",
        "|-------|--------|--------|---------|",
    ]
    for model_name in SOURCES:
        entry = credits.get(model_name)
        if not isinstance(entry, dict):
            continue
        credit = entry["credit"].removeprefix("Photo: ").replace("|", "/")
        licence = f"[link]({entry['license_url']})" if entry.get("license_url") else "-"
        lines.append(f"| {model_name} | {credit} | [Commons page]({entry['source']}) | {licence} |")
    (Path(settings.BASE_DIR) / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def shrink_existing():
    """Re-encode any already-downloaded photos at web size."""
    for path in image_dir().glob("*.jpg"):
        _save_web_jpeg(path.read_bytes(), path)


def attach_all():
    """Point CarModel rows at photos already on disk. Returns the number attached."""
    from .models import CarModel

    folder = image_dir()
    credits_path = folder / "credits.json"
    credits = json.loads(credits_path.read_text(encoding="utf-8")) if credits_path.exists() else {}
    attached = 0
    for cm in CarModel.objects.all():
        filename = f"{slugify(cm.name)}.jpg"
        if (folder / filename).exists():
            entry = credits.get(cm.name) or {}
            if isinstance(entry, str):  # older credits.json format
                entry = {"credit": entry}
            cm.image.name = f"car_models/{filename}"
            cm.image_credit = entry.get("credit", "")
            cm.image_source = entry.get("source", "")
            cm.save(update_fields=["image", "image_credit", "image_source"])
            attached += 1
    return attached
