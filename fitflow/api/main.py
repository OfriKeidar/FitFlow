"""App entry point. Run with:  uvicorn fitflow.api.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from fitflow.api.routes import chat, coach, foods, log, users
from fitflow.db.models import Base
from fitflow.db.seed import seed_foods
from fitflow.db.session import SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO(migrations): switch to Alembic once the schema stabilizes.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_foods(db)
    yield


app = FastAPI(title="FitFlow", version="0.1.0", lifespan=lifespan)
for module in (users, foods, log, coach, chat):
    app.include_router(module.router)
