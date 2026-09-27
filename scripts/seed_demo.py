"""Create the demo account locally (the data itself is defined in fitflow/db/demo.py).

Usage:  .venv/Scripts/python -m scripts.seed_demo
Then log in to the app as demo@fitflow.app / demo1234.
"""

from fitflow.api.main import init_db
from fitflow.db.demo import DEMO_EMAIL, DEMO_PASSWORD, TRUE_TDEE, create_demo_user, demo_exists
from fitflow.db.session import SessionLocal


def main() -> None:
    init_db()  # tables + food database
    with SessionLocal() as db:
        if demo_exists(db):
            print(f"The demo account already exists. Log in with: {DEMO_EMAIL} / {DEMO_PASSWORD}")
            return
        user = create_demo_user(db)
        print(f"Demo user created (formula TDEE: {user.tdee:.0f}, true TDEE: {TRUE_TDEE})")
        print(f"Log in with: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
