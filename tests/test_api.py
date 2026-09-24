from datetime import timedelta

import pytest

from tests.conftest import food_id


def test_create_user_computes_initial_tdee(client, user):
    me = client.get("/me", headers=user).json()
    assert me["tdee"] == pytest.approx(1805 * 1.2)  # Mifflin-St Jeor x sedentary


def test_invalid_profile_is_rejected(client):
    r = client.post("/users", json={"name": "A", "sex": "male", "age": 5, "height_cm": 180, "weight_kg": 80,
                                    "activity": "sedentary", "goal": "maintain"})
    assert r.status_code == 422


def test_unknown_user_gets_404(client):
    assert client.get("/me", headers={"X-User-Id": "999"}).status_code == 404


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
    other = client.post("/users", json={"name": "B", "sex": "female", "age": 30, "height_cm": 165, "weight_kg": 60,
                                        "activity": "light", "goal": "maintain"}).json()
    r = client.delete(f"/log/food/{entry['id']}", headers={"X-User-Id": str(other["id"])})
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
    body = {"name": "A", "sex": "male", "age": 30, "height_cm": 180, "weight_kg": 80, "activity": "light"}
    assert client.post("/users", json=body | {"goal": "cut", "target_weight_kg": 85}).status_code == 422
    assert client.post("/users", json=body | {"goal": "bulk", "target_weight_kg": 75}).status_code == 422
    assert client.post("/users", json=body | {"goal": "cut"}).status_code == 422  # target required
    assert client.post("/users", json=body | {"goal": "maintain"}).status_code == 201


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
