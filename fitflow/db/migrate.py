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


def migrate(engine: Engine) -> None:
    # National food database (which source a food came from, and its code there)
    _add_column_if_missing(engine, "foods", "source", "VARCHAR(20) NOT NULL DEFAULT 'fitflow'")
    _add_column_if_missing(engine, "foods", "external_code", "INTEGER")

    # Health Connect sync (workout source + id in the source app)
    _add_column_if_missing(engine, "workouts", "source", "VARCHAR(20) NOT NULL DEFAULT 'manual'")
    _add_column_if_missing(engine, "workouts", "external_id", "VARCHAR(200)")
    with engine.begin() as conn:
        # Unique per user; rows without an external id (NULL) never conflict, in SQLite and PostgreSQL alike.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_workouts_user_external ON workouts (user_id, external_id)"
        ))
