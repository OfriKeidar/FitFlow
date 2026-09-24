from dataclasses import asdict
from datetime import date, datetime

from fastapi import APIRouter, Query

from fitflow.api.deps import DB, CurrentUser, Today
from fitflow.api.schemas import (
    DailyStatusOut, InsightOut, MacrosOut, MealSuggestionOut, ProgressOut, SuggestedItem,
    TargetUpdateOut, WeekOut, WeightOut,
)
from fitflow.services import coach, tracking

router = APIRouter(tags=["coach"])


@router.get("/today", response_model=DailyStatusOut)
def today_status(user: CurrentUser, db: DB, today: Today, day: date | None = None):
    """The dashboard. Also re-learns the TDEE if a week has passed since the last update."""
    update = coach.update_targets_if_due(db, user, today)
    status = tracking.daily_status(db, user, day or today)
    return DailyStatusOut.model_validate(status).model_copy(
        update={"target_update": TargetUpdateOut(**asdict(update)) if update else None}
    )


@router.get("/coach/meal-suggestion", response_model=MealSuggestionOut)
def meal_suggestion(
    user: CurrentUser, db: DB, today: Today,
    hour: int | None = Query(default=None, ge=0, le=23),
):
    hour = datetime.now().hour if hour is None else hour
    remaining = tracking.daily_status(db, user, today).remaining
    suggestion = coach.suggest_meal_now(db, user, today, hour)
    return MealSuggestionOut(
        items=[SuggestedItem(food=p.food.name, serving=p.food.serving, servings=n) for p, n in suggestion.items],
        totals=MacrosOut.model_validate(suggestion.totals),
        remaining_before=MacrosOut.model_validate(remaining),
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


@router.get("/progress", response_model=ProgressOut)
def progress(user: CurrentUser, db: DB):
    p = coach.progress(db, user)
    return ProgressOut(
        weigh_ins=[WeightOut.model_validate(w) for w in p.weigh_ins],
        trend=[WeightOut(day=w.day, weight_kg=round(w.weight_kg, 2)) for w in p.trend],
        tdee=round(p.tdee),
    )
