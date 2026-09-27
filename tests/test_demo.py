"""The demo account: created on startup when SEED_DEMO is set, only once."""

from fastapi.testclient import TestClient

from fitflow.api.main import app
from fitflow.db.demo import DEMO_EMAIL, DEMO_PASSWORD
from fitflow.db.models import Base
from fitflow.db.session import engine


def test_demo_account_is_created_once_on_startup(monkeypatch):
    Base.metadata.drop_all(engine)
    monkeypatch.setenv("SEED_DEMO", "true")
    with TestClient(app):
        pass
    with TestClient(app) as client:  # a second startup must not fail or duplicate the account
        r = client.post("/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200
        headers = {"Authorization": f"Bearer {r.json()['token']}"}
        assert len(client.get("/progress", headers=headers).json()["weigh_ins"]) >= 30
        assert client.get("/coach/insights", headers=headers).json()  # the data produces insights
