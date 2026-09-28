"""Convert the Israeli national nutrition database (Tzameret) into fitflow/data/foods_tzameret.json.

Source: Israeli Ministry of Health, "מאגר התזונה הלאומי", https://data.gov.il/dataset/nutrition-database
(open license). Download these three CSVs from that page into data_raw/tzameret/ (any file names):
    - the foods file with nutrients per 100 g   (has columns Code, shmmitzrach, food_energy, ...)
    - the unit names file                        (smlmida, shmmida)
    - the unit weights per food file             (mmitzrach, mida, mishkal)

Usage:  .venv/Scripts/python -m scripts.import_tzameret

The output ships with the app (it's small: names, 4 macros and units per food). The app loads it into
the database on startup - see fitflow/db/seed.py.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data_raw" / "tzameret"
OUT = ROOT / "fitflow" / "data" / "foods_tzameret.json"

# The first digit of the food code is its group (USDA-style numbering used by Tzameret).
GROUP_TO_CATEGORY = {
    "1": "dairy", "2": "protein", "3": "protein", "4": "protein", "5": "carb",
    "6": "fruit", "7": "vegetable", "8": "fat", "9": "carb",
}
SKIP_UNITS = {"גרמים", "קילוגרם"}  # not real portions
MAX_NAME = 100  # the foods.name column length


def read_csv(name_hint: str, columns: set[str]) -> list[dict]:
    """Find the downloaded file by its exact set of key columns - the portal's file names change between
    versions, and matching on one column isn't enough (the recipes file also has a 'mishkal' column)."""
    for path in RAW.glob("*.csv"):
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if columns == set(reader.fieldnames or []) & (columns | {"mitzbsisi"}):
                return list(reader)
    raise SystemExit(f"Missing the {name_hint} CSV in {RAW} (a file with columns {sorted(columns)})")


def number(value: str) -> float:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0.0


def convert(foods: list[dict], unit_names: list[dict], unit_weights: list[dict]) -> list[list]:
    """Rows of [code, name, kcal, protein, carbs, fat, category, [[unit, grams], ...]] per 100 g."""
    names = {row["smlmida"]: row["shmmida"].strip() for row in unit_names}
    units = defaultdict(list)
    for row in unit_weights:
        unit, grams = names.get(row["mida"]), number(row["mishkal"])
        if unit and unit not in SKIP_UNITS and 0 < grams < 2000:
            units[row["mmitzrach"]].append([unit, grams])

    rows = []
    for food in foods:
        name = " ".join(food["shmmitzrach"].split())  # collapse double spaces
        if not name or not food["food_energy"].strip():
            continue
        if name.upper().startswith("FFQ"):
            continue  # food-frequency-questionnaire groups ("mixed stews, such as ..."), not real foods
        rows.append([
            int(food["Code"]), name, number(food["food_energy"]), number(food["protein"]),
            number(food["carbohydrates"]), number(food["total_fat"]),
            GROUP_TO_CATEGORY.get(food["smlmitzrach"][:1], "carb"),
            sorted(units.get(food["Code"], []), key=lambda u: u[1])[:8],
        ])
    return rows


def main() -> None:
    rows = convert(
        read_csv("foods", {"Code", "shmmitzrach", "food_energy"}),
        read_csv("unit names", {"smlmida", "shmmida"}),
        read_csv("unit weights", {"mmitzrach", "mida", "mishkal"}),  # not the recipes file ("mitzbsisi")
    )
    too_long = [r[1] for r in rows if len(r[1]) > MAX_NAME]
    if too_long:  # PostgreSQL enforces the column length (SQLite doesn't) - fail here, not in production
        raise SystemExit(f"{len(too_long)} names exceed {MAX_NAME} characters, e.g. {too_long[0]!r}")
    OUT.write_text(json.dumps({
        "source": "Israeli Ministry of Health - national nutrition database (Tzameret), data.gov.il/dataset/nutrition-database",
        "per": "100 g",
        "columns": ["code", "name", "kcal", "protein_g", "carbs_g", "fat_g", "category", "units"],
        "foods": rows,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(rows)} foods to {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
