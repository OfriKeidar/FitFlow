from fastapi import APIRouter, HTTPException

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import (
    CustomFoodLogIn, FoodLogIn, FoodLogOut, FoodLogUpdate, WeightIn, WeightOut, WorkoutIn,
    WorkoutOut, WorkoutUpdate,
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
    servings = body.servings or tracking.servings_for(food, body.grams)
    return tracking.log_food(db, user, food, servings, body.day or today)


@router.post("/custom-food", response_model=FoodLogOut, status_code=201)
def log_custom_food(body: CustomFoodLogIn, user: CurrentUser, db: DB, today: Today):
    total = Macros(body.kcal, body.protein_g, body.carbs_g, body.fat_g)
    return tracking.log_custom_food(db, user, body.description, 1, total, body.day or today)


@router.patch("/food/{entry_id}", response_model=FoodLogOut)
def update_food(entry_id: int, body: FoodLogUpdate, user: CurrentUser, db: DB):
    entry = _own_or_404(db, FoodLogEntry, entry_id, user.id)
    return tracking.update_food_entry(db, entry, body.model_dump(exclude_unset=True))


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


@router.patch("/workout/{entry_id}", response_model=WorkoutOut)
def update_workout(entry_id: int, body: WorkoutUpdate, user: CurrentUser, db: DB):
    entry = _own_or_404(db, WorkoutEntry, entry_id, user.id)
    if body.activity is not None and body.activity not in ACTIVITIES:
        raise HTTPException(422, f"Unknown activity. Known: {sorted(ACTIVITIES)}")
    return tracking.update_workout(db, user, entry, body.activity, body.minutes)


@router.delete("/workout/{entry_id}", status_code=204)
def delete_workout(entry_id: int, user: CurrentUser, db: DB):
    _delete_own(db, WorkoutEntry, entry_id, user.id)


@router.post("/weight", response_model=WeightOut, status_code=201)
def log_weight(body: WeightIn, user: CurrentUser, db: DB, today: Today):
    return tracking.log_weight(db, user, body.weight_kg, body.day or today)


def _own_or_404(db: DB, model, entry_id: int, user_id: int):
    entry = db.get(model, entry_id)
    # Same 404 for "doesn't exist" and "belongs to someone else" - don't leak which one.
    if entry is None or entry.user_id != user_id:
        raise HTTPException(404, "Entry not found")
    return entry


def _delete_own(db: DB, model, entry_id: int, user_id: int) -> None:
    db.delete(_own_or_404(db, model, entry_id, user_id))
    db.commit()
