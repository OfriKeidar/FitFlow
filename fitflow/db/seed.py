"""Loads the food databases into the foods table.

1. foods.json - our short list of common foods with natural servings ("1 large egg"). Loaded into
   an empty table.
2. External databases, per 100 g, each loaded once. Generated offline by scripts in scripts/:
   - foods_tzameret.json - the Israeli national nutrition database (~4,500 generic foods, with
     household units). scripts/import_tzameret.py
   - foods_off.json - Open Food Facts (branded Israeli products, with barcodes).
     scripts/import_openfoodfacts.py
"""

import json
import os
from pathlib import Path

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from fitflow.db.models import Food, FoodLogEntry, FoodUnit

# Shipped inside the package (see [tool.setuptools.package-data]), so it works when installed too.
DATA = Path(__file__).resolve().parent.parent / "data"
FOODS_FILE = DATA / "foods.json"
# Loaded in this order. On a name collision the earlier one wins: generic foods before branded products.
FOOD_DATABASES = {"tzameret": DATA / "foods_tzameret.json", "off": DATA / "foods_off.json"}
ALL_MEALS = "BREAKFAST,LUNCH,DINNER,SNACK"


def seed_foods(db: Session) -> int:
    if db.scalar(select(Food.id).limit(1)) is not None:
        return 0
    rows = json.loads(FOODS_FILE.read_text(encoding="utf-8"))
    db.add_all(Food(**row | {"meals": ",".join(row["meals"])}) for row in rows)
    db.commit()
    return len(rows)


def sync_curated_weights(db: Session) -> None:
    """Our foods existed before they had a weight per serving: copy it from foods.json on every start,
    so a database created earlier gets the new values too (idempotent)."""
    weights = {r["name"]: r["grams_per_serving"] for r in json.loads(FOODS_FILE.read_text(encoding="utf-8"))}
    for food in db.scalars(select(Food).where(Food.source == "fitflow")):
        if food.name in weights and food.grams_per_serving != weights[food.name]:
            food.grams_per_serving = weights[food.name]
    db.commit()


def backfill_log_grams(db: Session) -> None:
    """Entries logged before weights existed: grams = servings x the food's weight per serving."""
    weight = select(Food.grams_per_serving).where(Food.id == FoodLogEntry.food_id).scalar_subquery()
    db.execute(
        update(FoodLogEntry)
        .where(FoodLogEntry.grams.is_(None), FoodLogEntry.food_id.is_not(None))
        .values(grams=FoodLogEntry.servings * weight)
    )
    db.commit()


def food_databases_enabled() -> bool:
    # Tests turn it off: loading thousands of foods before every test would make the suite slow.
    return os.getenv("SEED_FOOD_DATABASES", "true").lower() not in ("0", "false", "no")


def seed_food_database(db: Session, source: str, path: Path | None = None) -> int:
    """Add the foods of one external database that aren't loaded yet (by their code), so a bigger
    version of the file adds only the new foods on the next start. Foods whose name we already have
    (e.g. "שמן זית") keep the existing version. Uses bulk inserts: thousands of foods + units in a couple
    of statements, not one by one."""
    path = path or FOOD_DATABASES[source]
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    loaded = set(db.scalars(select(Food.external_code).where(Food.source == source)))
    existing = set(db.scalars(select(Food.name)))
    rows = [r for r in data["foods"] if r[0] not in loaded and r[1] not in existing]
    if not rows:
        return 0

    db.execute(insert(Food), [
        {"name": name, "serving": "100 גרם", "kcal": kcal, "protein_g": protein, "carbs_g": carbs,
         "fat_g": fat, "category": category, "meals": ALL_MEALS, "source": source, "external_code": code}
        for code, name, kcal, protein, carbs, fat, category, _units in rows
    ])
    ids = dict(db.execute(select(Food.external_code, Food.id).where(Food.source == source)).all())
    unit_rows = [
        {"food_id": ids[code], "name": unit, "grams": grams}
        for code, *_, units in rows for unit, grams in units
    ]
    if unit_rows:
        db.execute(insert(FoodUnit), unit_rows)
    db.commit()
    return len(rows)
