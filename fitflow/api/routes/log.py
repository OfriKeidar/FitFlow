from fastapi import APIRouter, HTTPException

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import (
    CustomFoodLogIn, FoodLogIn, FoodLogOut, WeightIn, WeightOut, WorkoutIn, WorkoutOut,
)
from fitflow.db.models import Food, FoodLogEntry, WorkoutEntry
from fitflow.domain.activity import ACTIVITIES
from fitflow.domain.models import Macros
from fitflow.services import tracking

router = APIRouter(prefix="/log", tags=["log"])


@router.post("/food", response_model=FoodLogOut, status_code=201)
def log_food(body: FoodLogIn, user: CurrentUser, db: DB, today: Today):
    food = db.get(Food, body.food_id)
    if food is None:
        raise HTTPException(404, "Food not found")
    return tracking.log_food(db, user, food, body.servings, body.day or today)


@router.post("/custom-food", response_model=FoodLogOut, status_code=201)
def log_custom_food(body: CustomFoodLogIn, user: CurrentUser, db: DB, today: Today):
    total = Macros(body.kcal, body.protein_g, body.carbs_g, body.fat_g)
    return tracking.log_custom_food(db, user, body.description, 1, total, body.day or today)


@router.delete("/food/{entry_id}", status_code=204)
def delete_food(entry_id: int, user: CurrentUser, db: DB):
    _delete_own(db, FoodLogEntry, entry_id, user.id)


@router.get("/activities", response_model=dict[str, str])
def list_activities():
    """Known workout types and their category."""
    return {name: a.category.value for name, a in ACTIVITIES.items()}


@router.post("/workout", response_model=WorkoutOut, status_code=201)
def log_workout(body: WorkoutIn, user: CurrentUser, db: DB, today: Today):
    if body.activity not in ACTIVITIES:
        raise HTTPException(422, f"Unknown activity. Known: {sorted(ACTIVITIES)}")
    return tracking.log_workout(db, user, body.activity, body.minutes, body.day or today)


@router.delete("/workout/{entry_id}", status_code=204)
def delete_workout(entry_id: int, user: CurrentUser, db: DB):
    _delete_own(db, WorkoutEntry, entry_id, user.id)


@router.post("/weight", response_model=WeightOut, status_code=201)
def log_weight(body: WeightIn, user: CurrentUser, db: DB, today: Today):
    return tracking.log_weight(db, user, body.weight_kg, body.day or today)


def _delete_own(db: DB, model, entry_id: int, user_id: int) -> None:
    entry = db.get(model, entry_id)
    # Same 404 for "doesn't exist" and "belongs to someone else" - don't leak which one.
    if entry is None or entry.user_id != user_id:
        raise HTTPException(404, "Entry not found")
    db.delete(entry)
    db.commit()
