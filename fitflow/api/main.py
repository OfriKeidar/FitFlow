"""The API app. Run locally with:  uvicorn fitflow.api.main:app --reload
(In production, fitflow/web.py serves this app under /api together with the built frontend.)"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fitflow.api.routes import auth, chat, coach, foods, log, users
from fitflow.db.demo import create_demo_user, demo_exists
from fitflow.db.migrate import migrate
from fitflow.db.models import Base
from fitflow.db.seed import FOOD_DATABASES, food_databases_enabled, seed_food_database, seed_foods
from fitflow.db.session import SessionLocal, engine


# Our own log lines (fitflow.*) at INFO: model timings, fallbacks, LLM errors.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("fitflow").setLevel(logging.INFO)


def init_db() -> None:
    # TODO(migrations): switch to Alembic once the schema stabilizes.
    Base.metadata.create_all(engine)  # creates missing tables
    migrate(engine)                    # adds missing columns to existing tables
    with SessionLocal() as db:
        seed_foods(db)
        for source in FOOD_DATABASES if food_databases_enabled() else ():
            if added := seed_food_database(db, source):
                logging.getLogger("fitflow").info("loaded %d foods from %s", added, source)
        # On a public demo server, create the demo account visitors can log in with.
        if os.getenv("SEED_DEMO", "").lower() in ("1", "true", "yes") and not demo_exists(db):
            create_demo_user(db)
            logging.getLogger("fitflow").info("created the demo account")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FitFlow", version="0.1.0", lifespan=lifespan)

for module in (auth, users, foods, log, coach, chat):
    app.include_router(module.router)


@app.get("/health", tags=["ops"])
def health():
    """For the hosting platform's health checks: 200 means the process is up."""
    return {"status": "ok"}
