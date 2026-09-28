"""The startup migration must upgrade a database created before the national-food columns existed."""

from sqlalchemy import create_engine, inspect, text

from fitflow.db.migrate import migrate


def test_adds_missing_columns_to_an_old_table_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # the foods table as it looked before
        conn.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name VARCHAR(100))"))
        conn.execute(text("INSERT INTO foods VALUES (1, 'ביצה')"))

    migrate(engine)
    migrate(engine)  # a second start must not fail

    assert {"source", "external_code"} <= {c["name"] for c in inspect(engine).get_columns("foods")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT source FROM foods WHERE id = 1")).scalar() == "fitflow"  # existing row
