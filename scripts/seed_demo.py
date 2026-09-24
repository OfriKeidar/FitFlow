"""Create a demo user with 5 weeks of realistic history, so every screen has something to show.

Usage:  .venv/Scripts/python -m scripts.seed_demo
Then log in to the app as demo@fitflow.app / demo1234.

The simulated user:
  - cuts from 84 kg, with a real TDEE of ~2650 kcal (higher than the formula's guess, so the
    adaptive algorithm has something to discover)
  - eats more on Fridays and Saturdays, and misses protein on rest days (so insights appear)
  - trains 4 times a week: 3 strength sessions + 1 run
"""

import random
from datetime import date, timedelta

from fitflow.db.models import Base, Food, PantryItem
from fitflow.db.seed import seed_foods
from fitflow.db.session import SessionLocal, engine
from fitflow.domain.models import KCAL_PER_KG, Macros
from fitflow.services import auth, tracking

DEMO_EMAIL, DEMO_PASSWORD = "demo@fitflow.app", "demo1234"
DAYS = 35
TRUE_TDEE = 2650
rng = random.Random(7)  # fixed seed: the same demo data every run


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_foods(db)
        today = date.today()
        start = today - timedelta(days=DAYS)

        user = tracking.create_user(
            db, start, email=DEMO_EMAIL, password_hash=auth.hash_password(DEMO_PASSWORD), name="דניאל", sex="male", age=27, height_cm=178, start_weight_kg=84.0,
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

        # Today: breakfast and lunch already logged, so the dashboard shows progress.
        today_meals = [("ביצה", 2), ("לחם מלא", 2), ("קוטג' 5%", 1), ("חזה עוף", 1.5), ("אורז לבן", 1.5), ("סלט ירקות", 1)]
        for name, servings in today_meals:
            tracking.log_food(db, user, db.query(Food).filter_by(name=name).one(), servings, today)

        pantry = ["חזה עוף", "ביצה", "אורז לבן", "בטטה", "קוטג' 5%", "סלט ירקות", "טונה במים", "לחם מלא"]
        for name in pantry:
            food = db.query(Food).filter_by(name=name).one()
            db.add(PantryItem(user_id=user.id, food_id=food.id, max_servings=3))

        # Last TDEE update long ago -> the next dashboard visit triggers the adaptive update.
        user.tdee_updated_on = start
        db.commit()

        print(f"Demo user created (formula TDEE: {user.tdee:.0f}, true TDEE: {TRUE_TDEE})")
        print(f"Log in with: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
