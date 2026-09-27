"""A demo account with 5 weeks of realistic history, so every screen has something to show.

Created by `python -m scripts.seed_demo` locally, or automatically at startup when SEED_DEMO=true
(so a freshly deployed server has an account visitors can try: demo@fitflow.app / demo1234).

The simulated user:
  - cuts from 84 kg, with a real TDEE of ~2650 kcal (higher than the formula's guess, so the
    adaptive algorithm has something to discover)
  - eats more on Fridays and Saturdays, and misses protein on rest days (so insights appear)
  - trains 4 times a week: 3 strength sessions + 1 run
"""

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from fitflow.db.models import Food, PantryItem, User
from fitflow.domain.models import KCAL_PER_KG, Macros
from fitflow.services import auth, tracking

DEMO_EMAIL, DEMO_PASSWORD = "demo@fitflow.app", "demo1234"
DAYS = 35
TRUE_TDEE = 2650


def demo_exists(db: Session) -> bool:
    return db.scalar(select(User.id).where(User.email == DEMO_EMAIL)) is not None


def create_demo_user(db: Session, today: date | None = None) -> User:
    """Assumes the tables and the food database exist (see api/main.py: init_db)."""
    rng = random.Random(7)  # fixed seed: the same demo data every time
    today = today or date.today()
    start = today - timedelta(days=DAYS)

    user = tracking.create_user(
        db, start, email=DEMO_EMAIL, password_hash=auth.hash_password(DEMO_PASSWORD),
        name="דניאל", sex="male", age=27, height_cm=178, start_weight_kg=84.0,
        activity="sedentary", goal="cut", target_weight_kg=76.0, pace="recommended",
        weigh_in_frequency="daily", weekly_workout_goal=4,
    )

    weight = 84.0
    for n in range(DAYS):
        day = start + timedelta(days=n)
        is_weekend = day.weekday() in (4, 5)  # Friday, Saturday
        trains = day.weekday() in (6, 1, 3, 4)  # Sun, Tue, Thu strength + Fri run

        intake = rng.gauss(2750 if is_weekend else 2050, 120)
        protein = rng.gauss(175, 12) if trains else rng.gauss(120, 12)
        fat = intake * 0.3 / 9
        carbs = (intake - protein * 4 - fat * 9) / 4
        tracking.log_custom_food(db, user, "ארוחות היום", 1, Macros(intake, protein, carbs, fat), day)

        burned = 0.0
        if trains:
            activity = "running" if day.weekday() == 4 else "strength_training"
            burned = tracking.log_workout(db, user, activity, 50, day).kcal

        # Weight follows energy balance, plus daily water noise on the scale.
        weight += (intake - TRUE_TDEE - burned) / KCAL_PER_KG
        tracking.log_weight(db, user, round(weight + rng.uniform(-0.6, 0.6), 1), day)

    def food(name: str) -> Food:
        return db.scalars(select(Food).where(Food.name == name)).one()

    # Today: breakfast and lunch already logged, so the dashboard shows progress.
    for name, servings in [("ביצה", 2), ("לחם מלא", 2), ("קוטג' 5%", 1), ("חזה עוף", 1.5), ("אורז לבן", 1.5), ("סלט ירקות", 1)]:
        tracking.log_food(db, user, food(name), servings, today)

    for name in ["חזה עוף", "ביצה", "אורז לבן", "בטטה", "קוטג' 5%", "סלט ירקות", "טונה במים", "לחם מלא"]:
        db.add(PantryItem(user_id=user.id, food_id=food(name).id, max_servings=3))

    # Last TDEE update long ago -> the next dashboard visit triggers the adaptive update.
    user.tdee_updated_on = start
    db.commit()
    return user
