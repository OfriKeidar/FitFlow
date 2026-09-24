import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# SQLite for local development; set DATABASE_URL to a PostgreSQL URL in production.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fitflow.db")


def normalize_url(url: str) -> str:
    """Hosting platforms hand out "postgres://..." URLs; SQLAlchemy needs the driver named explicitly."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str = DATABASE_URL, **kwargs) -> Engine:
    url = normalize_url(url)
    if url.startswith("sqlite"):
        kwargs.setdefault("connect_args", {"check_same_thread": False})
    else:
        kwargs.setdefault("pool_pre_ping", True)  # replace connections the database closed while idle
    if url == "sqlite://":  # in-memory DB (tests): share one connection, or each one gets an empty DB
        kwargs.setdefault("poolclass", StaticPool)
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one DB session per request, always closed afterwards."""
    with SessionLocal() as db:
        yield db
