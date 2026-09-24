"""Loads the starter food database (fitflow/data/foods.json) into an empty foods table."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.db.models import Food

# Shipped inside the package (see [tool.setuptools.package-data]), so it works when installed too.
FOODS_FILE = Path(__file__).resolve().parent.parent / "data" / "foods.json"


def seed_foods(db: Session) -> int:
    if db.scalar(select(Food.id).limit(1)) is not None:
        return 0
    rows = json.loads(FOODS_FILE.read_text(encoding="utf-8"))
    db.add_all(Food(**row | {"meals": ",".join(row["meals"])}) for row in rows)
    db.commit()
    return len(rows)
