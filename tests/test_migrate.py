"""The startup migration must upgrade a database created before the Health Connect and national-food columns existed."""

from sqlalchemy import create_engine, inspect, text

from fitflow.db.migrate import migrate


def test_adds_missing_columns_to_an_old_table_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # the workouts table as it looked before
        conn.execute(text(
            "CREATE TABLE workouts (id INTEGER PRIMARY KEY, user_id INTEGER, day DATE, activity VARCHAR(50), "
            "category VARCHAR(20), minutes FLOAT, kcal FLOAT)"
        ))
        conn.execute(text("INSERT INTO workouts VALUES (1, 1, '2026-09-01', 'running', 'cardio', 30, 300)"))
        conn.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name VARCHAR(100))"))
        conn.execute(text("INSERT INTO foods VALUES (1, 'ביצה')"))

    migrate(engine)
    migrate(engine)  # a second start must not fail

    columns = {c["name"] for c in inspect(engine).get_columns("workouts")}
    assert {"source", "external_id"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT source FROM workouts WHERE id = 1")).scalar() == "manual"  # existing row

    assert {"source", "external_code"} <= {c["name"] for c in inspect(engine).get_columns("foods")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT source FROM foods WHERE id = 1")).scalar() == "fitflow"
