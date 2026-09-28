"""Loads the food databases into the foods table.

1. foods.json - our short list of common foods with natural servings ("1 large egg"). Loaded into
   an empty table.
2. foods_tzameret.json - the Israeli national nutrition database (~4,500 foods, per 100 g, with
   household units). Loaded once; generated from the Ministry of Health's CSVs by
   scripts/import_tzameret.py.
"""

import json
import os
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from fitflow.db.models import Food, FoodUnit

# Shipped inside the package (see [tool.setuptools.package-data]), so it works when installed too.
DATA = Path(__file__).resolve().parent.parent / "data"
FOODS_FILE = DATA / "foods.json"
TZAMERET_FILE = DATA / "foods_tzameret.json"
ALL_MEALS = "BREAKFAST,LUNCH,DINNER,SNACK"


def seed_foods(db: Session) -> int:
    if db.scalar(select(Food.id).limit(1)) is not None:
        return 0
    rows = json.loads(FOODS_FILE.read_text(encoding="utf-8"))
    db.add_all(Food(**row | {"meals": ",".join(row["meals"])}) for row in rows)
    db.commit()
    return len(rows)


def tzameret_enabled() -> bool:
    # Tests turn it off: loading 4,500 foods before every test would make the suite slow.
    return os.getenv("SEED_TZAMERET", "true").lower() not in ("0", "false", "no")


def seed_tzameret(db: Session, path: Path = TZAMERET_FILE) -> int:
    """Add the national database once. Foods whose name we already have (e.g. "שמן זית") keep our
    version. Uses bulk inserts: ~4,500 foods + ~15,000 units in a couple of statements, not one by one."""
    if db.scalar(select(Food.id).where(Food.source == "tzameret").limit(1)) is not None:
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = set(db.scalars(select(Food.name)))
    rows = [r for r in data["foods"] if r[1] not in existing]

    db.execute(insert(Food), [
        {"name": name, "serving": "100 גרם", "kcal": kcal, "protein_g": protein, "carbs_g": carbs,
         "fat_g": fat, "category": category, "meals": ALL_MEALS, "source": "tzameret", "external_code": code}
        for code, name, kcal, protein, carbs, fat, category, _units in rows
    ])
    ids = dict(db.execute(select(Food.external_code, Food.id).where(Food.source == "tzameret")).all())
    unit_rows = [
        {"food_id": ids[code], "name": unit, "grams": grams}
        for code, *_, units in rows for unit, grams in units
    ]
    if unit_rows:
        db.execute(insert(FoodUnit), unit_rows)
    db.commit()
    return len(rows)
