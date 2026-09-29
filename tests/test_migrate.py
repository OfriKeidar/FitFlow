"""The startup migration must upgrade a database created before the newer columns existed."""

from sqlalchemy import create_engine, inspect, text

from fitflow.db.migrate import migrate


def test_adds_missing_columns_to_an_old_table_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:  # the tables as they looked before
        conn.execute(text("CREATE TABLE foods (id INTEGER PRIMARY KEY, name VARCHAR(100))"))
        conn.execute(text("INSERT INTO foods VALUES (1, 'ביצה')"))
        conn.execute(text("CREATE TABLE food_log (id INTEGER PRIMARY KEY, food_id INTEGER, servings FLOAT)"))

    migrate(engine)
    migrate(engine)  # a second start must not fail

    columns = {c["name"] for c in inspect(engine).get_columns("foods")}
    assert {"source", "external_code", "grams_per_serving"} <= columns
    assert "grams" in {c["name"] for c in inspect(engine).get_columns("food_log")}
    with engine.connect() as conn:  # existing rows get the defaults
        assert conn.execute(text("SELECT source, grams_per_serving FROM foods WHERE id = 1")).one() == ("fitflow", 100)
