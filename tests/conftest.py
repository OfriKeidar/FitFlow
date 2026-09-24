import os

# Must be set before the app is imported, so tests never touch the real DB file.
os.environ["DATABASE_URL"] = "sqlite://"

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from fitflow.api.deps import get_today  # noqa: E402
from fitflow.api.main import app  # noqa: E402
from fitflow.db.models import Base  # noqa: E402
from fitflow.db.session import engine  # noqa: E402


class Clock:
    """Lets a test move 'today' forward."""
    def __init__(self, today: date):
        self.today = today


@pytest.fixture
def clock():
    return Clock(date(2026, 9, 6))  # a Sunday


@pytest.fixture
def client(clock):
    Base.metadata.drop_all(engine)  # fresh DB per test
    app.dependency_overrides[get_today] = lambda: clock.today
    with TestClient(app) as c:  # runs lifespan: create tables + seed foods
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def user(client):
    """Creates a user and returns request headers authenticating as them."""
    r = client.post("/users", json={
        "name": "Dana", "sex": "male", "age": 25, "height_cm": 180, "weight_kg": 80,
        "activity": "sedentary", "goal": "cut", "target_weight_kg": 72,
    })
    assert r.status_code == 201, r.text
    return {"X-User-Id": str(r.json()["id"])}


def food_id(client, name: str) -> int:
    return next(f["id"] for f in client.get("/foods", params={"q": name}).json() if f["name"] == name)
