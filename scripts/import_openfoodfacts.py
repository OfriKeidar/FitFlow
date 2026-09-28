"""Convert Israeli products from Open Food Facts into fitflow/data/foods_off.json.

Source: Open Food Facts (https://world.openfoodfacts.org), a crowd-sourced database of packaged products.
License: Open Database License (ODbL) - the derived file must credit the source and stay under the ODbL.

It complements the national database: Tzameret has generic foods ("יוגורט 3%"), Open Food Facts has
branded products ("יוגורט יופלה תות"), with Hebrew names and barcodes.

Usage:  .venv/Scripts/python -m scripts.import_openfoodfacts          (download what's missing, then convert)
        .venv/Scripts/python -m scripts.import_openfoodfacts convert  (convert the pages already downloaded)

Downloading is resumable: each page of the search API is saved to data_raw/openfoodfacts/ (gitignored),
and pages already there are skipped. The API allows ~10 searches a minute, so the script waits between pages.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "openfoodfacts"
OUT = ROOT / "fitflow" / "data" / "foods_off.json"

API = "https://world.openfoodfacts.org/api/v2/search"
FIELDS = "code,product_name,product_name_he,brands,categories_tags,serving_quantity,nutriments"
PAGE_SIZE = 100
SECONDS_BETWEEN_PAGES = 7  # stays under the API's rate limit for searches
USER_AGENT = "FitFlow/0.1 (portfolio project; https://github.com/OfriKeidar/FitFlow)"

HEBREW = re.compile(r"[֐-׿]")
MAX_NAME = 100  # the foods.name column length

# Categories: Open Food Facts tags first; if none match, decide by which macro gives most of the calories.
TAG_TO_CATEGORY = [
    ("en:dairies", "dairy"), ("en:cheeses", "dairy"), ("en:yogurts", "dairy"), ("en:milks", "dairy"),
    ("en:meats", "protein"), ("en:fishes", "protein"), ("en:eggs", "protein"), ("en:legumes", "protein"),
    ("en:fruits", "fruit"), ("en:vegetables", "vegetable"),
    ("en:fats", "fat"), ("en:nuts", "fat"), ("en:spreads", "fat"),
]


# --- download ---

def fetch_page(page: int, attempts: int = 20) -> dict:
    """One page of search results. The public API is often overloaded (503) or rate limited (429),
    so retry with a growing wait: 30 s, 60 s, 90 s... up to 5 minutes."""
    url = f"{API}?countries_tags_en=israel&fields={FIELDS}&page_size={PAGE_SIZE}&page={page}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == attempts:
                raise
            wait = min(30 * attempt, 300)
            print(f"page {page}: {e} - retrying in {wait} s", flush=True)
            time.sleep(wait)


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    page, page_count = 1, None
    while page_count is None or page <= page_count:
        path = RAW / f"page_{page:03d}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = fetch_page(page)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            print(f"page {page}: {len(data['products'])} products", flush=True)
            time.sleep(SECONDS_BETWEEN_PAGES)
        page_count = -(-data["count"] // PAGE_SIZE)  # ceiling division
        page += 1


# --- convert ---

def hebrew_name(product: dict) -> str | None:
    """The Hebrew name, with the brand in parentheses when it isn't already part of the name."""
    name = next((n for n in (product.get("product_name_he"), product.get("product_name"))
                 if n and HEBREW.search(n)), None)
    if name is None:
        return None
    name = " ".join(name.split())
    brand = " ".join((product.get("brands") or "").split(",")[0].split())
    if brand and brand not in name:
        name = f"{name} ({brand})"
    return name if len(name) <= MAX_NAME else None


def macros(product: dict) -> tuple[float, float, float, float] | None:
    """kcal, protein, carbs, fat per 100 g - or None if missing or not believable."""
    n = product.get("nutriments") or {}
    try:
        values = [float(n[key]) for key in ("energy-kcal_100g", "proteins_100g", "carbohydrates_100g", "fat_100g")]
    except (KeyError, TypeError, ValueError):
        return None
    kcal, protein, carbs, fat = values
    # Under 5 kcal (water, salt, diet soda) adds nothing to calorie tracking, and has no main macro.
    if not 5 <= kcal <= 900 or min(protein, carbs, fat) < 0 or protein + carbs + fat > 100:
        return None
    # Crowd-sourced data has typos. Energy must roughly match the macros (4/4/9 kcal per gram);
    # a big mismatch means a wrong value somewhere (e.g. kJ entered as kcal).
    if abs(4 * protein + 4 * carbs + 9 * fat - kcal) > 0.25 * kcal + 25:
        return None
    return tuple(round(v, 1) for v in values)


def category(product: dict, protein: float, carbs: float, fat: float) -> str:
    tags = set(product.get("categories_tags") or [])
    for tag, name in TAG_TO_CATEGORY:
        if tag in tags:
            return name
    by_kcal = {"protein": 4 * protein, "carb": 4 * carbs, "fat": 9 * fat}
    return max(by_kcal, key=by_kcal.get)


def convert(products: list[dict]) -> list[list]:
    """Rows of [barcode, name, kcal, protein, carbs, fat, category, [[unit, grams], ...]] per 100 g."""
    rows, seen_codes, seen_names = [], set(), set()
    for p in products:
        code, name, values = p.get("code", ""), hebrew_name(p), macros(p)
        if not code.isdigit() or name is None or values is None:
            continue
        if code in seen_codes or name in seen_names:  # the same product listed twice
            continue
        seen_codes.add(code)
        seen_names.add(name)
        kcal, protein, carbs, fat = values
        units = []
        try:
            serving = float(p.get("serving_quantity") or 0)
        except (TypeError, ValueError):
            serving = 0
        if 5 <= serving < 2000:  # smaller "servings" are usually typos
            units.append(["מנה", round(serving, 1)])  # the serving printed on the package
        rows.append([int(code), name, kcal, protein, carbs, fat, category(p, protein, carbs, fat), units])
    return rows


def main() -> None:
    if "convert" not in sys.argv[1:]:
        download()
    pages = sorted(RAW.glob("page_*.json"))
    if not pages:
        raise SystemExit(f"No downloaded pages in {RAW}")
    products = [p for path in pages for p in json.loads(path.read_text(encoding="utf-8"))["products"]]
    rows = convert(products)
    OUT.write_text(json.dumps({
        "source": "Open Food Facts (https://world.openfoodfacts.org), Open Database License (ODbL)",
        "per": "100 g",
        "columns": ["code", "name", "kcal", "protein_g", "carbs_g", "fat_g", "category", "units"],
        "foods": rows,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(products)} products -> {len(rows)} foods with a Hebrew name and believable values -> {OUT}")


if __name__ == "__main__":
    main()
