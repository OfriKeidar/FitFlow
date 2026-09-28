"""The national food database (Tzameret): loading it, and ranking search results sensibly."""

import pytest
from sqlalchemy import func, select

from fitflow.ai.tools import ToolExecutor
from fitflow.db.models import Food, FoodUnit, User
from fitflow.db.seed import seed_tzameret
from fitflow.db.session import SessionLocal


@pytest.fixture
def national_db(client):
    """The regular test DB plus the ~4,500 national foods (other tests skip them for speed)."""
    with SessionLocal() as db:
        added = seed_tzameret(db)
    return added


def test_loads_the_national_database_once(national_db):
    assert national_db > 4000
    with SessionLocal() as db:
        assert seed_tzameret(db) == 0  # the second start adds nothing
        assert db.scalar(select(func.count()).select_from(FoodUnit)) > 9000
        # A name we already had keeps our version (with its natural serving), not a duplicate.
        olive_oil = db.scalars(select(Food).where(Food.name == "שמן זית")).all()
        assert len(olive_oil) == 1 and olive_oil[0].source == "fitflow"


def test_search_ranks_the_common_food_first(client, national_db):
    names = [f["name"] for f in client.get("/foods", params={"q": "ביצה"}).json()]
    assert names[0] == "ביצה"
    # Dried egg powder (605 kcal / 100 g) must not outrank real eggs.
    assert not any("מיובש" in n for n in names[:5])


def test_search_finds_dishes_only_the_national_database_has(client, national_db):
    names = [f["name"] for f in client.get("/foods", params={"q": "שקשוקה"}).json()]
    assert names and all("שקשוקה" in n for n in names[:3])


def test_processed_forms_rank_first_when_asked_for(client, national_db):
    names = [f["name"] for f in client.get("/foods", params={"q": "אבקת חלב"}).json()]
    assert names and ("אבקת" in names[0] or "אבקה" in names[0])


def test_ai_search_includes_household_units(client, user, national_db):
    with SessionLocal() as db:
        me = db.scalars(select(User)).first()
        results = ToolExecutor(db, me, None, 12)._search("שקשוקה")
    national = next(r for r in results if r["serving"] == "100 גרם")
    assert national["units_grams"] and all(grams > 0 for grams in national["units_grams"].values())
