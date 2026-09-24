"""Loads the starter food database (data/foods.json) into an empty foods table."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.db.models import Food

FOODS_FILE = Path(__file__).resolve().parents[2] / "data" / "foods.json"


def seed_foods(db: Session) -> int:
    if db.scalar(select(Food.id).limit(1)) is not None:
        return 0
    rows = json.loads(FOODS_FILE.read_text(encoding="utf-8"))
    db.add_all(Food(**row | {"meals": ",".join(row["meals"])}) for row in rows)
    db.commit()
    return len(rows)
