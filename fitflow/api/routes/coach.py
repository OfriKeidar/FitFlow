from dataclasses import asdict
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import (
    DailyStatusOut, FitMealIn, InsightOut, MacrosOut, MealSuggestionOut, PlanOut, ProgressOut,
    SuggestedItem, TargetUpdateOut, WeekOut, WeightOut, WorkoutStatsOut,
)
from fitflow.db.models import Food
from fitflow.services import coach, tracking

router = APIRouter(tags=["coach"])


@router.get("/today", response_model=DailyStatusOut)
def today_status(user: CurrentUser, db: DB, today: Today, day: date | None = None):
    """The dashboard. Also re-learns the TDEE if a week has passed since the last update.

    The update runs lazily on the first request of the day, but the response doesn't depend on
    which request ran it: calling this twice returns the same data (idempotent GET).
    """
    coach.update_targets_if_due(db, user, today)
    status = tracking.daily_status(db, user, day or today)
    change = coach.todays_target_change(user, today)
    return DailyStatusOut.model_validate(status).model_copy(
        update={"target_update": TargetUpdateOut(**asdict(change)) if change else None}
    )


@router.get("/coach/meal-suggestion", response_model=MealSuggestionOut)
def meal_suggestion(
    user: CurrentUser, db: DB, today: Today,
    hour: int | None = Query(default=None, ge=0, le=23),
    exclude: list[str] = Query(default=[], description='Earlier suggestions, as food ids "1,4,7" - one per parameter'),
):
    """The best meal from the pantry. Pass earlier suggestions in `exclude` to get the next-best one."""
    hour = datetime.now().hour if hour is None else hour
    names = {item.food_id: item.food.name for item in user.pantry}
    combinations = [
        frozenset(names[int(i)] for i in group.split(",") if i.strip().isdigit() and int(i) in names)
        for group in exclude
    ]
    plan = coach.suggest_meal_now(db, user, today, hour, [c for c in combinations if c])
    return _meal_out(db, user, today, plan, {name: food_id for food_id, name in names.items()})


@router.post("/coach/fit-meal", response_model=MealSuggestionOut)
def fit_meal(body: FitMealIn, user: CurrentUser, db: DB, today: Today):
    """'I'm thinking of eating these foods' -> the amounts that fit what's left today."""
    foods = [db.get(Food, food_id) for food_id in dict.fromkeys(body.food_ids)]  # unique, in order
    if any(food is None for food in foods):
        raise HTTPException(404, "Food not found")
    hour = datetime.now().hour if body.hour is None else body.hour
    plan = coach.fit_meal_now(db, user, today, hour, foods)
    return _meal_out(db, user, today, plan, {food.name: food.id for food in foods})


def _meal_out(db: DB, user: CurrentUser, today, plan, ids: dict[str, int]) -> MealSuggestionOut:
    """`ids` maps food names back to database ids (domain Food objects carry no id)."""
    remaining = tracking.daily_status(db, user, today).remaining
    return MealSuggestionOut(
        items=[SuggestedItem(food_id=ids[p.food.name], food=p.food.name, serving=p.food.serving, servings=n)
               for p, n in plan.suggestion.items],
        totals=MacrosOut.model_validate(plan.suggestion.totals),
        meal_target=MacrosOut.model_validate(plan.target),
        remaining_today=MacrosOut.model_validate(remaining),
    )


@router.get("/coach/insights", response_model=list[InsightOut])
def insights(user: CurrentUser, db: DB, today: Today):
    return coach.insights(db, user, today)


@router.get("/workouts/week", response_model=WeekOut)
def workouts_week(user: CurrentUser, db: DB, today: Today, day: date | None = None):
    week = coach.week_summary(db, user, day or today)
    return WeekOut(
        week_start=week.week_start,
        counts={c.value: n for c, n in week.counts.items()},
        goal=week.goal,
        workouts=week.workouts,
    )


@router.get("/workouts/stats", response_model=WorkoutStatsOut)
def workouts_stats(user: CurrentUser, db: DB, today: Today):
    return asdict(coach.stats(db, user, today))


@router.get("/progress", response_model=ProgressOut)
def progress(user: CurrentUser, db: DB, today: Today):
    p = coach.progress(db, user, today)
    return ProgressOut(
        weigh_ins=[WeightOut.model_validate(w) for w in p.weigh_ins],
        trend=[WeightOut(day=w.day, weight_kg=round(w.weight_kg, 2)) for w in p.trend],
        tdee=round(p.tdee),
        start_weight_kg=user.start_weight_kg,
        target_weight_kg=user.target_weight_kg,
        plan=PlanOut(**asdict(p.plan)),
    )
