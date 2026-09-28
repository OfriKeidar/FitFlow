"""The national food database (Tzameret): loading it, and ranking search results sensibly."""

import json

import pytest
from sqlalchemy import func, select

from fitflow.ai.tools import ToolExecutor
from fitflow.db.models import Food, FoodUnit, User
from fitflow.db.seed import seed_food_database
from fitflow.db.session import SessionLocal
from scripts.import_openfoodfacts import convert as convert_off


@pytest.fixture
def national_db(client):
    """The regular test DB plus the ~4,500 national foods (other tests skip them for speed)."""
    with SessionLocal() as db:
        added = seed_food_database(db, "tzameret")
    return added


def test_loads_the_national_database_once(national_db):
    assert national_db > 4000
    with SessionLocal() as db:
        assert seed_food_database(db, "tzameret") == 0  # the second start adds nothing
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


# --- Open Food Facts (branded products) ---

def off_product(**overrides):
    product = {
        "code": "7290000000001", "product_name_he": "יוגורט תות", "brands": "יופלה",
        "categories_tags": ["en:dairies"], "serving_quantity": "150",
        "nutriments": {"energy-kcal_100g": 100, "proteins_100g": 4, "carbohydrates_100g": 15, "fat_100g": 2.5},
    }
    return product | overrides


def test_off_conversion_keeps_good_products():
    [row] = convert_off([off_product()])
    assert row == [7290000000001, "יוגורט תות (יופלה)", 100, 4, 15, 2.5, "dairy", [["מנה", 150]]]


def test_off_conversion_filters_bad_data():
    bad = [
        off_product(code="1", product_name_he=None, product_name="Strawberry yogurt"),  # no Hebrew name
        off_product(code="2", nutriments={"energy-kcal_100g": 100}),                     # macros missing
        # kJ typed as kcal: 418 "kcal" but the macros only add up to ~100
        off_product(code="3", nutriments={"energy-kcal_100g": 418, "proteins_100g": 4,
                                          "carbohydrates_100g": 15, "fat_100g": 2.5}),
        off_product(code="4", nutriments={"energy-kcal_100g": 100, "proteins_100g": 60,
                                          "carbohydrates_100g": 60, "fat_100g": 2.5}),   # > 100 g per 100 g
    ]
    assert convert_off(bad) == []
    # The same product listed twice is kept once.
    assert len(convert_off([off_product(), off_product()])) == 1


def test_off_category_falls_back_to_the_main_macro():
    oil = off_product(categories_tags=[], nutriments={"energy-kcal_100g": 884, "proteins_100g": 0,
                                                      "carbohydrates_100g": 0, "fat_100g": 100})
    assert convert_off([oil])[0][6] == "fat"


def test_generic_food_ranks_before_branded_products(client, national_db, tmp_path):
    path = tmp_path / "off.json"
    path.write_text(json.dumps({"foods": convert_off([off_product(product_name_he="חומוס", brands="צבר")])}),
                    encoding="utf-8")
    with SessionLocal() as db:
        assert seed_food_database(db, "off", path) == 1
    names = [f["name"] for f in client.get("/foods", params={"q": "חומוס"}).json()]
    assert names[0] == "חומוס"  # ours first
    assert names.index("חומוס (צבר)") > names.index("חומוס יבש")  # generic before branded
    # ...but with the brand in the query, names containing every word come first.
    names = [f["name"] for f in client.get("/foods", params={"q": "חומוס צבר"}).json()]
    assert "חומוס (צבר)" in names and all("צבר" in name for name in names[:4])
