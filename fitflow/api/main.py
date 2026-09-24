"""The API app. Run locally with:  uvicorn fitflow.api.main:app --reload
(In production, fitflow/web.py serves this app under /api together with the built frontend.)"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fitflow.api.routes import auth, chat, coach, foods, log, users
from fitflow.db.models import Base
from fitflow.db.seed import seed_foods
from fitflow.db.session import SessionLocal, engine


# Our own log lines (fitflow.*) at INFO: model timings, fallbacks, LLM errors.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("fitflow").setLevel(logging.INFO)


def init_db() -> None:
    # TODO(migrations): switch to Alembic once the schema stabilizes.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_foods(db)


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
