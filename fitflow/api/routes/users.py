from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import (
    GoalName, PaceName, PlanOut, UserOut, UserUpdate, check_target,
)
from fitflow.domain.models import ActivityLevel, Goal, Pace, Profile, Sex
from fitflow.services import coach, tracking

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: CurrentUser, db: DB):
    changes = body.model_dump(exclude_unset=True)
    goal = changes.get("goal", user.goal)
    target = changes.get("target_weight_kg", user.target_weight_kg)
    if goal == "maintain":
        changes["target_weight_kg"] = target = None
    try:
        check_target(goal, tracking.current_weight(db, user), target)
    except ValueError as e:
        raise HTTPException(422, str(e))
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    return user


@router.get("/plan-preview", response_model=PlanOut)
def plan_preview(
    today: Today,
    goal: GoalName,
    weight_kg: float = Query(ge=35, le=300),
    target_weight_kg: float | None = Query(default=None, ge=35, le=300),
    pace: PaceName = "recommended",
):
    """Used by onboarding to show "you'll reach your target around <date>" before signing up."""
    # Only weight, goal, target and pace affect the plan; the other fields are placeholders.
    profile = Profile(
        sex=Sex.MALE, age=30, height_cm=175, weight_kg=weight_kg, activity=ActivityLevel.SEDENTARY,
        goal=Goal(goal), target_weight_kg=target_weight_kg, pace=Pace(pace),
    )
    return PlanOut(**asdict(coach.plan_for(profile, today)))
