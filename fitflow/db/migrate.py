"""Small schema migrations for databases that already exist (e.g. the one on Render).

`Base.metadata.create_all` creates missing TABLES, but never adds COLUMNS to a table that already
exists. Each step here is idempotent: it checks the live schema first and only changes what's missing,
so it's safe to run on every start.

(A project with many schema changes would use Alembic, which versions migrations. For a handful of
additive changes, this keeps things simple and visible.)
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

log = logging.getLogger("fitflow.db")


def _add_column_if_missing(engine: Engine, table: str, column: str, ddl: str) -> None:
    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    if column not in existing:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        log.info("migration: added %s.%s", table, column)


def _widen_to_bigint(engine: Engine, table: str, column: str) -> None:
    """PostgreSQL only: SQLite's INTEGER already holds 64-bit values."""
    if engine.dialect.name != "postgresql":
        return
    types = {c["name"]: str(c["type"]) for c in inspect(engine).get_columns(table)}
    if types.get(column) == "INTEGER":
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT"))
        log.info("migration: %s.%s is now BIGINT", table, column)


def migrate(engine: Engine) -> None:
    # National food database (which source a food came from, and its code there)
    _add_column_if_missing(engine, "foods", "source", "VARCHAR(20) NOT NULL DEFAULT 'fitflow'")
    _add_column_if_missing(engine, "foods", "external_code", "BIGINT")
    _widen_to_bigint(engine, "foods", "external_code")  # created as INTEGER before barcodes were stored

