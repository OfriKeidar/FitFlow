from datetime import timedelta

import pytest
from sqlalchemy import select

from tests.conftest import PROFILE, food_id, register


def test_create_user_computes_initial_tdee(client, user):
    me = client.get("/me", headers=user).json()
    assert me["tdee"] == pytest.approx(1805 * 1.2)  # Mifflin-St Jeor x sedentary


def test_invalid_profile_is_rejected(client):
    r = client.post("/auth/register", json=PROFILE | {"age": 5, "email": "a@example.com", "password": "secret123"})
    assert r.status_code == 422


def test_foods_are_seeded_and_searchable(client):
    names = [f["name"] for f in client.get("/foods", params={"q": "עוף"}).json()]
    assert "חזה עוף" in names


def test_logging_food_updates_daily_status(client, user):
    before = client.get("/today", headers=user).json()
    client.post("/log/food", headers=user, json={"food_id": food_id(client, "ביצה"), "servings": 2})
    after = client.get("/today", headers=user).json()

    assert after["eaten"]["kcal"] == 144
    assert after["remaining"]["kcal"] == pytest.approx(before["remaining"]["kcal"] - 144, abs=0.1)
    assert [e["description"] for e in after["entries"]] == ["ביצה"]


def test_workout_raises_target_and_is_categorized(client, user):
    base = client.get("/today", headers=user).json()["target"]["kcal"]
    r = client.post("/log/workout", headers=user, json={"activity": "running", "minutes": 30})
    assert r.json()["category"] == "cardio"
    assert client.get("/today", headers=user).json()["target"]["kcal"] == pytest.approx(base + 352, abs=0.1)


def test_unknown_workout_is_rejected(client, user):
    r = client.post("/log/workout", headers=user, json={"activity": "chess", "minutes": 30})
    assert r.status_code == 422


def test_cannot_delete_someone_elses_entry(client, user):
    entry = client.post("/log/custom-food", headers=user, json={"description": "פיצה", "kcal": 300}).json()
    other = register(client, email="other@example.com")
    r = client.delete(f"/log/food/{entry['id']}", headers=other)
    assert r.status_code == 404


def test_meal_suggestion_uses_pantry(client, user):
    for name, n in [("חזה עוף", 3), ("אורז לבן", 3), ("סלט ירקות", 2), ("דגני בוקר", 2)]:
        client.put(f"/pantry/{food_id(client, name)}", headers=user, json={"max_servings": n})

    r = client.get("/coach/meal-suggestion", headers=user, params={"hour": 20}).json()
    foods = {i["food"] for i in r["items"]}
    assert foods and foods <= {"חזה עוף", "אורז לבן", "סלט ירקות"}  # no cereal for dinner
    assert all(i["food_id"] == food_id(client, i["food"]) for i in r["items"])


def test_disliked_food_is_never_suggested(client, user):
    chicken = food_id(client, "חזה עוף")
    client.put(f"/pantry/{chicken}", headers=user, json={"max_servings": 3})
    client.put(f"/pantry/{food_id(client, 'טונה במים')}", headers=user, json={"max_servings": 2})
    client.put(f"/disliked/{chicken}", headers=user)

    r = client.get("/coach/meal-suggestion", headers=user, params={"hour": 20}).json()
    assert "חזה עוף" not in {i["food"] for i in r["items"]}


def test_weekly_workout_summary(client, user):
    client.post("/log/workout", headers=user, json={"activity": "strength_training", "minutes": 60})
    client.post("/log/workout", headers=user, json={"activity": "running", "minutes": 30})
    week = client.get("/workouts/week", headers=user).json()
    assert week["counts"] == {"strength": 1, "cardio": 1, "other": 0}


def test_tdee_adapts_after_weeks_of_data(client, user, clock):
    """Eat 2000/day and lose 0.5 kg/week => real TDEE ~2550, higher than the 2166 formula guess."""
    start = clock.today
    for n in range(28):
        day = (start + timedelta(days=n)).isoformat()
        client.post("/log/custom-food", headers=user, json={"description": "יום", "kcal": 2000, "day": day})
        if n % 7 == 0:
            client.post("/log/weight", headers=user, json={"weight_kg": 80 - 0.5 * n / 7, "day": day})

    initial = client.get("/me", headers=user).json()["tdee"]
    clock.today = start + timedelta(days=28)
    update = client.get("/today", headers=user).json()["target_update"]

    assert update["previous_tdee"] == pytest.approx(initial)
    assert update["tdee"] == pytest.approx(initial + 150)  # the data says more, but we move carefully (capped step)

    # Idempotent: a second request the same day reports the same update, and doesn't update again.
    assert client.get("/today", headers=user).json()["target_update"] == update
    clock.today += timedelta(days=1)
    assert client.get("/today", headers=user).json()["target_update"] is None


def test_no_banner_when_update_had_too_little_data(client, user, clock):
    clock.today += timedelta(days=7)  # an update is due, but nothing was logged
    assert client.get("/today", headers=user).json()["target_update"] is None


def test_target_must_match_goal(client):
    body = PROFILE | {"email": "a@example.com", "password": "secret123"}
    assert client.post("/auth/register", json=body | {"goal": "cut", "target_weight_kg": 85}).status_code == 422
    assert client.post("/auth/register", json=body | {"goal": "bulk", "target_weight_kg": 75}).status_code == 422
    assert client.post("/auth/register", json=body | {"goal": "cut", "target_weight_kg": None}).status_code == 422
    maintain = body | {"goal": "maintain", "target_weight_kg": None}
    assert client.post("/auth/register", json=maintain).status_code == 201


def test_plan_preview_estimates_the_target_date(client, clock):
    plan = client.get("/plan-preview", params={"goal": "cut", "weight_kg": 80, "target_weight_kg": 72}).json()
    assert plan["weekly_rate_kg"] == 0.6 and plan["weeks_to_target"] == 14
    assert plan["target_date"] == (clock.today + timedelta(weeks=14)).isoformat()


def test_switching_to_maintain_clears_the_target(client, user):
    me = client.patch("/me", headers=user, json={"goal": "maintain"}).json()
    assert me["goal"] == "maintain" and me["target_weight_kg"] is None


def test_progress_includes_plan(client, user):
    p = client.get("/progress", headers=user).json()
    assert p["start_weight_kg"] == 80 and p["target_weight_kg"] == 72
    assert p["plan"]["weeks_to_target"] == 14


def test_workout_stats(client, user):
    client.post("/log/workout", headers=user, json={"activity": "running", "minutes": 30})
    stats = client.get("/workouts/stats", headers=user).json()
    assert stats["total_workouts"] == 1 and stats["days_since_last"] == 0
    assert stats["favorite_activity"] == "running"


def test_edit_food_servings_scales_values(client, user):
    entry = client.post("/log/food", headers=user, json={"food_id": food_id(client, "ביצה"), "servings": 2}).json()
    edited = client.patch(f"/log/food/{entry['id']}", headers=user, json={"servings": 3}).json()
    assert edited["servings"] == 3 and edited["kcal"] == pytest.approx(216)  # 72 per egg


def test_edit_food_with_exact_values(client, user):
    entry = client.post("/log/custom-food", headers=user, json={"description": "שניצל", "kcal": 300}).json()
    edited = client.patch(f"/log/food/{entry['id']}", headers=user, json={"kcal": 420, "protein_g": 30}).json()
    assert edited["kcal"] == 420 and edited["protein_g"] == 30
    assert client.get("/today", headers=user).json()["eaten"]["kcal"] == 420


def test_edit_workout_recomputes_calories(client, user):
    w = client.post("/log/workout", headers=user, json={"activity": "running", "minutes": 30}).json()
    edited = client.patch(f"/log/workout/{w['id']}", headers=user, json={"minutes": 60}).json()
    assert edited["kcal"] == pytest.approx(2 * w["kcal"])


def test_cannot_edit_someone_elses_entry(client, user):
    entry = client.post("/log/custom-food", headers=user, json={"description": "x", "kcal": 100}).json()
    other = register(client, email="other@example.com")
    assert client.patch(f"/log/food/{entry['id']}", headers=other, json={"kcal": 1}).status_code == 404


def test_fixing_the_signup_weight(client, user):
    """Typed 87 instead of 78 at sign-up: fixing it changes the start weight and the TDEE."""
    before = client.get("/me", headers=user).json()["tdee"]
    me = client.patch("/me", headers=user, json={"weight_kg": 78, "target_weight_kg": 72}).json()
    progress = client.get("/progress", headers=user).json()
    assert progress["start_weight_kg"] == 78 and [w["weight_kg"] for w in progress["weigh_ins"]] == [78]
    assert me["tdee"] < before  # a lighter body burns less


def test_editing_profile_details(client, user):
    me = client.patch("/me", headers=user, json={"height_cm": 175, "age": 30, "sex": "female"}).json()
    assert (me["height_cm"], me["age"], me["sex"]) == (175, 30, "female")


def test_different_meal_suggestion(client, user):
    for name in ("חזה עוף", "טונה במים", "אורז לבן", "בטטה", "סלט ירקות"):
        client.put(f"/pantry/{food_id(client, name)}", headers=user, json={"max_servings": 2})
    first = client.get("/coach/meal-suggestion", headers=user, params={"hour": 20}).json()
    ids = ",".join(str(i["food_id"]) for i in first["items"])
    second = client.get("/coach/meal-suggestion", headers=user, params={"hour": 20, "exclude": ids}).json()
    assert second["items"] and {i["food"] for i in second["items"]} != {i["food"] for i in first["items"]}


def test_fit_my_meal(client, user):
    ids = [food_id(client, "חזה עוף"), food_id(client, "אורז לבן")]
    r = client.post("/coach/fit-meal", headers=user, json={"food_ids": ids, "hour": 20}).json()
    assert {i["food"] for i in r["items"]} == {"חזה עוף", "אורז לבן"}
    assert r["totals"]["protein_g"] > 0.7 * r["meal_target"]["protein_g"]


# --- logging by weight ---

def test_log_food_by_grams(client, user):
    entry = client.post("/log/food", headers=user, json={"food_id": food_id(client, "אורז לבן"), "grams": 150}).json()
    assert entry["grams"] == 150 and entry["servings"] == 1.5 and entry["kcal"] == pytest.approx(195)  # 130 / 100 g


def test_log_food_needs_exactly_one_amount(client, user):
    rice = food_id(client, "אורז לבן")
    assert client.post("/log/food", headers=user, json={"food_id": rice}).status_code == 422
    assert client.post("/log/food", headers=user, json={"food_id": rice, "grams": 100, "servings": 1}).status_code == 422


def test_servings_are_converted_to_grams_by_the_food_weight(client, user):
    entry = client.post("/log/food", headers=user, json={"food_id": food_id(client, "ביצה"), "servings": 2}).json()
    assert entry["grams"] == 100  # a large egg is 50 g


def test_edit_food_grams_scales_values(client, user):
    entry = client.post("/log/food", headers=user, json={"food_id": food_id(client, "אורז לבן"), "grams": 100}).json()
    edited = client.patch(f"/log/food/{entry['id']}", headers=user, json={"grams": 250}).json()
    assert edited["grams"] == 250 and edited["servings"] == 2.5 and edited["kcal"] == pytest.approx(325)


def test_food_search_returns_the_weight_of_a_serving(client):
    [bread] = [f for f in client.get("/foods", params={"q": "לחם מלא"}).json() if f["name"] == "לחם מלא"]
    assert bread["grams_per_serving"] == 30 and bread["units"] == []


def test_today_shows_the_planned_deficit(client, user):
    today = client.get("/today", headers=user).json()
    # Cutting at the recommended pace: 0.75% of 80 kg a week = 0.6 kg -> 0.6 x 7700 / 7 = 660 kcal a day.
    assert today["planned_balance"] == pytest.approx(-660, abs=1)
    client.post("/log/workout", headers=user, json={"activity": "running", "minutes": 30})
    # A workout raises both the burn and the target, so the plan doesn't change.
    assert client.get("/today", headers=user).json()["planned_balance"] == pytest.approx(-660, abs=1)


def test_startup_fills_weights_and_grams_of_an_older_database(client, user):
    from fitflow.db.models import Food, FoodLogEntry
    from fitflow.db.seed import backfill_log_grams, sync_curated_weights
    from fitflow.db.session import SessionLocal

    entry_id = client.post("/log/food", headers=user, json={"food_id": food_id(client, "ביצה"), "servings": 2}).json()["id"]
    with SessionLocal() as db:  # make it look like before this feature: no weights, no grams
        db.scalars(select(Food).where(Food.name == "ביצה")).one().grams_per_serving = 100
        db.get(FoodLogEntry, entry_id).grams = None
        db.commit()

        sync_curated_weights(db)
        backfill_log_grams(db)
        assert db.scalars(select(Food).where(Food.name == "ביצה")).one().grams_per_serving == 50
        assert db.get(FoodLogEntry, entry_id).grams == 100


def test_a_logged_food_offers_its_natural_portion_as_a_unit(client, user):
    egg = client.post("/log/food", headers=user, json={"food_id": food_id(client, "ביצה"), "servings": 1}).json()
    assert egg["units"] == [{"name": "גדולה", "grams": 50}]  # "1 גדולה" -> "גדולה"
    rice = client.post("/log/food", headers=user, json={"food_id": food_id(client, "אורז לבן"), "grams": 100}).json()
    assert rice["units"] == []  # "100 גרם מבושל": grams already say it
