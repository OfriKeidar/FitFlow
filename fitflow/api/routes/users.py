from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import (
    ExperienceName, GoalName, PaceName, PlanOut, UserOut, UserUpdate, check_target,
)
from fitflow.domain.energy import initial_tdee
from fitflow.domain.models import ActivityLevel, Experience, Goal, Pace, Profile, Sex
from fitflow.services import coach, tracking

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: UserUpdate, user: CurrentUser, db: DB, today: Today):
    changes = body.model_dump(exclude_unset=True)
    new_weight = changes.pop("weight_kg", None)
    goal = changes.get("goal", user.goal)
    target = changes.get("target_weight_kg", user.target_weight_kg)
    if goal == "maintain":
        changes["target_weight_kg"] = target = None
    try:
        check_target(goal, new_weight or tracking.current_weight(db, user), target)
    except ValueError as e:
        raise HTTPException(422, str(e))

    for field, value in changes.items():
        setattr(user, field, value)
    if new_weight is not None:
        tracking.correct_weight(db, user, new_weight, today)

    # Until the TDEE has been learned from real data, it comes from the formula - so a corrected
    # sex, age, height, activity level or weight must change it too.
    affects_formula = bool(changes.keys() & {"sex", "age", "height_cm", "activity"}) or new_weight is not None
    if affects_formula and user.tdee_previous is None:
        user.tdee = initial_tdee(tracking.profile_of(db, user))
    db.commit()
    return user


@router.get("/plan-preview", response_model=PlanOut)
def plan_preview(
    today: Today,
    goal: GoalName,
    weight_kg: float = Query(ge=35, le=300),
    target_weight_kg: float | None = Query(default=None, ge=35, le=300),
    pace: PaceName = "recommended",
    experience: ExperienceName = "intermediate",
):
    """Used by onboarding to show "you'll reach your target around <date>" before signing up."""
    # Only weight, goal, target, pace and experience affect the plan; the other fields are placeholders.
    profile = Profile(
        sex=Sex.MALE, age=30, height_cm=175, weight_kg=weight_kg, activity=ActivityLevel.SEDENTARY,
        goal=Goal(goal), target_weight_kg=target_weight_kg, pace=Pace(pace), experience=Experience(experience),
    )
    return PlanOut(**asdict(coach.plan_for(profile, today)))
