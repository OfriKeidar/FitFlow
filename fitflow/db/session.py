import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# SQLite for local development; set DATABASE_URL to a PostgreSQL URL in production.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fitflow.db")


def make_engine(url: str = DATABASE_URL, **kwargs) -> Engine:
    if url.startswith("sqlite"):
        kwargs.setdefault("connect_args", {"check_same_thread": False})
    if url == "sqlite://":  # in-memory DB (tests): share one connection, or each one gets an empty DB
        kwargs.setdefault("poolclass", StaticPool)
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one DB session per request, always closed afterwards."""
    with SessionLocal() as db:
        yield db
