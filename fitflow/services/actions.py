"""Pending actions: the human-in-the-loop gate between the AI and the database.

Flow:
    1. The AI calls a propose_* tool      -> propose_*() stores a PendingAction (nothing logged yet)
    2. The app shows the preview with Confirm / Reject buttons
    3. The user clicks Confirm            -> confirm()   runs the real logging code
       or Reject                          -> reject()    marks it rejected, nothing is written

Payloads are validated with Pydantic both when the AI proposes them and before they are executed.
"""

from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.db import models as db
from fitflow.domain.activity import ACTIVITIES, workout_kcal
from fitflow.domain.models import Macros
from fitflow.services import tracking
from fitflow.services.mappers import food_macros


# --- Payloads (what each kind of action contains) ---

class FoodItem(BaseModel):
    food_id: int
    grams: float = Field(gt=0, le=5000)


class FoodPayload(BaseModel):
    items: list[FoodItem] = Field(min_length=1, max_length=20)


class CustomFoodPayload(BaseModel):
    """A food that isn't in our database - the numbers are the AI's estimate, and say so."""
    description: str = Field(min_length=1, max_length=200)
    kcal: float = Field(ge=0, le=5000)
    protein_g: float = Field(ge=0, le=500)
    carbs_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=500)


class WorkoutPayload(BaseModel):
    activity: str
    minutes: float = Field(gt=0, le=600)


class WeightPayload(BaseModel):
    weight_kg: float = Field(ge=35, le=300)


PAYLOADS: dict[str, type[BaseModel]] = {
    "food": FoodPayload,
    "custom_food": CustomFoodPayload,
    "workout": WorkoutPayload,
    "weight": WeightPayload,
}


class ActionError(ValueError):
    """The proposed action is invalid (unknown food, unknown activity...).

    Error messages are English on purpose: they are read by the model (as tool errors), not by users.
    """


# --- Creating proposals ---

def _save(session: Session, user: db.User, day: date, kind: str, payload: BaseModel, summary: str) -> db.PendingAction:
    action = db.PendingAction(
        user_id=user.id, day=day, kind=kind, payload=payload.model_dump_json(), summary=summary,
    )
    session.add(action)
    session.flush()  # assigns action.id; committed together with the rest of the chat turn
    return action


def propose_food(session: Session, user: db.User, day: date, payload: FoodPayload) -> tuple[db.PendingAction, Macros]:
    lines, total = [], Macros(0, 0, 0, 0)
    for item in payload.items:
        food = session.get(db.Food, item.food_id)
        if food is None:
            raise ActionError(f"food_id {item.food_id} does not exist - use search_foods first")
        macros = food_macros(food).scale(tracking.servings_for(food, item.grams))
        total = total + macros
        lines.append(f"{food.name}, {item.grams:g} גרם: {macros.kcal:.0f} קק\"ל, {macros.protein_g:.0f} גר' חלבון")
    return _save(session, user, day, "food", payload, "\n".join(lines)), total


def propose_custom_food(session: Session, user: db.User, day: date, payload: CustomFoodPayload) -> db.PendingAction:
    summary = (f"{payload.description} (הערכה): {payload.kcal:.0f} קק\"ל, {payload.protein_g:.0f} גר' חלבון, "
               f"{payload.carbs_g:.0f} גר' פחמימות, {payload.fat_g:.0f} גר' שומן")
    return _save(session, user, day, "custom_food", payload, summary)


def propose_workout(session: Session, user: db.User, day: date, payload: WorkoutPayload) -> tuple[db.PendingAction, float]:
    if payload.activity not in ACTIVITIES:
        raise ActionError(f"Unknown activity {payload.activity!r}. Known: {sorted(ACTIVITIES)}")
    kcal = workout_kcal(payload.activity, payload.minutes, tracking.current_weight(session, user))
    summary = f"{payload.activity}, {payload.minutes:g} דק': כ-{kcal:.0f} קק\"ל נשרפו"
    return _save(session, user, day, "workout", payload, summary), kcal


def propose_weight(session: Session, user: db.User, day: date, payload: WeightPayload) -> db.PendingAction:
    return _save(session, user, day, "weight", payload, f"שקילה: {payload.weight_kg:g} ק\"ג")


# --- Resolving proposals (called when the user clicks a button) ---

def get_pending(session: Session, user: db.User, action_id: int) -> db.PendingAction | None:
    """Only the owner's still-pending actions can be confirmed or rejected."""
    return session.scalar(select(db.PendingAction).where(
        db.PendingAction.id == action_id,
        db.PendingAction.user_id == user.id,
        db.PendingAction.status == "pending",
    ))


def list_pending(session: Session, user: db.User) -> list[db.PendingAction]:
    return list(session.scalars(
        select(db.PendingAction)
        .where(db.PendingAction.user_id == user.id, db.PendingAction.status == "pending")
        .order_by(db.PendingAction.id)
    ))


def confirm(session: Session, user: db.User, action: db.PendingAction) -> None:
    payload = PAYLOADS[action.kind].model_validate_json(action.payload)

    if action.kind == "food":
        # Check every food exists BEFORE logging any, so we never log half a meal.
        foods = [(session.get(db.Food, item.food_id), item.grams) for item in payload.items]
        if any(food is None for food, _ in foods):
            raise ActionError("one of the foods no longer exists")
        for food, grams in foods:
            tracking.log_food(session, user, food, tracking.servings_for(food, grams), action.day)
    elif action.kind == "custom_food":
        total = Macros(payload.kcal, payload.protein_g, payload.carbs_g, payload.fat_g)
        tracking.log_custom_food(session, user, payload.description, 1, total, action.day)
    elif action.kind == "workout":
        tracking.log_workout(session, user, payload.activity, payload.minutes, action.day)
    elif action.kind == "weight":
        tracking.log_weight(session, user, payload.weight_kg, action.day)

    action.status = "confirmed"
    session.commit()


def reject(session: Session, action: db.PendingAction) -> None:
    action.status = "rejected"
    session.commit()
