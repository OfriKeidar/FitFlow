"""The tools the coach agent can call, and the code that runs them.

Two kinds of tools:
  - READ tools (search_foods, get_today_status, ...) return data straight away.
  - PROPOSE tools (propose_food_log, ...) never write to the log. They create a PendingAction
    that the user must confirm in the app. The model cannot bypass this - there is no tool
    that writes directly.

Every number the model reports comes from these tools (our deterministic code), not from the model.
The only exception is propose_custom_food, where the model estimates a food we don't have -
and that is explicitly labelled as an estimate for the user to confirm.
"""

import json
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fitflow.db import models as db
from fitflow.domain.activity import ACTIVITIES
from fitflow.services import actions, coach, tracking

# Tool definitions sent to the model. The descriptions matter: they are the model's only
# documentation of what each tool does and when to use it.
TOOLS = [
    {
        "name": "search_foods",
        "description": (
            "Search the food database by name (Hebrew). Returns matching foods with their id, "
            "serving size and nutrition per ONE serving. Search with the singular base form "
            "(e.g. 'ביצה' not 'ביצים'); if nothing matches, try a shorter word or a synonym."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Food name or part of it"}},
            "required": ["query"],
        },
    },
    {
        "name": "propose_food_log",
        "description": (
            "Propose logging foods that exist in the database. Nothing is saved until the user "
            "confirms in the app. `servings` is in the food's own serving unit (from search_foods), "
            "e.g. 2 for two eggs when the serving is '1 large'. Returns the nutrition totals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "food_id": {"type": "integer"},
                            "servings": {"type": "number", "description": "Number of servings, can be fractional"},
                        },
                        "required": ["food_id", "servings"],
                    },
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "propose_custom_food",
        "description": (
            "Propose logging a food that is NOT in the database, with your best nutrition estimate "
            "for the whole portion eaten. Use only after search_foods found no reasonable match. "
            "Tell the user the values are an estimate. Nothing is saved until the user confirms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "What was eaten, including the amount"},
                "kcal": {"type": "number"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
            },
            "required": ["description", "kcal", "protein_g", "carbs_g", "fat_g"],
        },
    },
    {
        "name": "propose_workout",
        "description": (
            "Propose logging a workout. Pick the closest activity from the list. Returns the calories "
            "burned (computed by our formula). Nothing is saved until the user confirms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "activity": {"type": "string", "enum": sorted(ACTIVITIES)},
                "minutes": {"type": "number"},
            },
            "required": ["activity", "minutes"],
        },
    },
    {
        "name": "propose_weight",
        "description": "Propose logging today's body weight in kg. Nothing is saved until the user confirms.",
        "input_schema": {
            "type": "object",
            "properties": {"weight_kg": {"type": "number"}},
            "required": ["weight_kg"],
        },
    },
    {
        "name": "get_today_status",
        "description": (
            "Today's targets, what was eaten, what remains (calories and macros), calories burned in "
            "workouts, and the energy balance (negative = deficit). Only includes CONFIRMED entries."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "suggest_meal",
        "description": (
            "Suggest a meal from the foods the user has at home. It aims for this meal's share of "
            "what remains today (based on the time of day), found by an optimization algorithm. "
            "Use when the user asks what to eat."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_week_workouts",
        "description": "This week's workouts (Sunday to Saturday) by category, and the user's weekly goal.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_insights",
        "description": "Statistical patterns in the user's last 4 weeks (weekend eating, protein on training days, streaks).",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _round(x: float) -> float:
    return round(x, 1)


def _macros(m) -> dict:
    return {"kcal": _round(m.kcal), "protein_g": _round(m.protein_g), "carbs_g": _round(m.carbs_g), "fat_g": _round(m.fat_g)}


@dataclass
class ToolExecutor:
    """Runs tool calls for one user during one chat turn."""
    session: Session
    user: db.User
    today: date
    hour: int
    proposed: list[db.PendingAction] = field(default_factory=list)  # actions created this turn

    def run(self, name: str, tool_input: dict) -> tuple[str, bool]:
        """Returns (result_text, is_error). Errors go back to the model so it can correct itself."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return f"Unknown tool: {name}", True
        try:
            return json.dumps(handler(**tool_input), ensure_ascii=False), False
        except (ValidationError, actions.ActionError, TypeError) as e:
            # TypeError = the model sent unexpected arguments. Treat model output as untrusted input.
            return f"Invalid input: {e}", True

    # --- read tools ---

    def _tool_search_foods(self, query: str) -> list[dict]:
        words = [w for w in query.split() if w]
        foods = self.session.scalars(
            select(db.Food).where(or_(*(db.Food.name.contains(w) for w in words))).limit(10)
        ) if words else []
        return [
            {"food_id": f.id, "name": f.name, "serving": f.serving, "kcal": f.kcal,
             "protein_g": f.protein_g, "carbs_g": f.carbs_g, "fat_g": f.fat_g}
            for f in foods
        ]

    def _tool_get_today_status(self) -> dict:
        s = tracking.daily_status(self.session, self.user, self.today)
        return {
            "goal": self.user.goal,
            "target": _macros(s.target),
            "eaten": _macros(s.eaten),
            "remaining": _macros(s.remaining),
            "workout_kcal": _round(s.workout_kcal),
            "energy_balance_kcal": _round(s.energy_balance),
            "logged_foods": [e.description for e in s.entries],
        }

    def _tool_suggest_meal(self) -> dict:
        plan = coach.suggest_meal_now(self.session, self.user, self.today, self.hour)
        suggestion = plan.suggestion
        if not suggestion.items:
            return {"items": [], "note": "No suggestion: the pantry is empty or nothing is left to eat today."}
        return {
            "items": [{"food": p.food.name, "serving": p.food.serving, "servings": n} for p, n in suggestion.items],
            "totals": _macros(suggestion.totals),
            "meal_target": _macros(plan.target),
        }

    def _tool_get_week_workouts(self) -> dict:
        week = coach.week_summary(self.session, self.user, self.today)
        return {
            "week_start": week.week_start.isoformat(),
            "counts": {c.value: n for c, n in week.counts.items()},
            "weekly_goal": week.goal,
            "workouts": [{"day": w.day.isoformat(), "activity": w.activity, "minutes": w.minutes} for w in week.workouts],
        }

    def _tool_get_insights(self) -> dict:
        found = coach.insights(self.session, self.user, self.today)
        return {"insights": [i.message for i in found] or ["Not enough data yet for insights."]}

    # --- propose tools ---

    def _tool_propose_food_log(self, items: list[dict]) -> dict:
        action, total = actions.propose_food(self.session, self.user, self.today, actions.FoodPayload(items=items))
        return self._proposed(action, totals=_macros(total))

    def _tool_propose_custom_food(self, **fields) -> dict:
        action = actions.propose_custom_food(self.session, self.user, self.today, actions.CustomFoodPayload(**fields))
        return self._proposed(action)

    def _tool_propose_workout(self, activity: str, minutes: float) -> dict:
        payload = actions.WorkoutPayload(activity=activity, minutes=minutes)
        action, kcal = actions.propose_workout(self.session, self.user, self.today, payload)
        return self._proposed(action, kcal_burned=_round(kcal), daily_target_increase_kcal=_round(kcal))

    def _tool_propose_weight(self, weight_kg: float) -> dict:
        action = actions.propose_weight(self.session, self.user, self.today, actions.WeightPayload(weight_kg=weight_kg))
        return self._proposed(action)

    def _proposed(self, action: db.PendingAction, **extra) -> dict:
        self.proposed.append(action)
        return {"status": "awaiting_user_confirmation", "action_id": action.id, "summary": action.summary, **extra}
