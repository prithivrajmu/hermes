import sqlite3

import pytest

from zaia import data


@pytest.fixture
def data_dir(tmp_path):
    """A scratch data dir with one dataset ("widgets") of two tables."""
    ds_dir = tmp_path / "widgets"
    ds_dir.mkdir()
    db_path = ds_dir / "widgets.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE raw_widgets (widget_id TEXT, name TEXT, price REAL)")
    con.executemany(
        "INSERT INTO raw_widgets VALUES (?, ?, ?)",
        [("W-1", "Gadget", 9.99), ("W-2", "Gizmo", 14.5), ("W-3", "Doohickey", 3.25)],
    )
    con.execute("CREATE TABLE raw_orders (order_id TEXT, widget_id TEXT)")
    con.executemany("INSERT INTO raw_orders VALUES (?, ?)", [("O-1", "W-1"), ("O-2", "W-1")])
    con.commit()
    con.close()
    return tmp_path


def test_discover_datasets(data_dir):
    found = data.discover_datasets(data_dir)
    assert set(found) == {"widgets"}
    assert found["widgets"].name == "widgets.db"


def test_discover_datasets_empty_dir(tmp_path):
    assert data.discover_datasets(tmp_path / "does_not_exist") == {}


def test_resolve_db_unknown_dataset(data_dir):
    with pytest.raises(ValueError, match="Unknown dataset"):
        data.resolve_db(data_dir, "nope")


def test_list_tables_and_row_counts(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    tables = {t["table"]: t["row_count"] for t in data.list_tables(con)}
    assert tables == {"raw_widgets": 3, "raw_orders": 2}


def test_table_schema(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    schema = data.table_schema(con, "raw_widgets")
    assert [c["name"] for c in schema["columns"]] == ["widget_id", "name", "price"]
    assert schema["sample_row"]["widget_id"] == "W-1"


def test_table_schema_infers_type_when_untyped(tmp_path):
    """zeus's own sqlite writer declares no column types (see zeus.core.writer),
    so table_schema must fall back to inferring from a sample value."""
    ds_dir = tmp_path / "raw"
    ds_dir.mkdir()
    con = sqlite3.connect(ds_dir / "raw.db")
    con.execute('CREATE TABLE "t" (id, label, amount)')
    con.execute("INSERT INTO t VALUES (1, 'x', 2.5)")
    con.commit()
    con.close()

    con = data.connect_ro(data.resolve_db(tmp_path, "raw"))
    schema = data.table_schema(con, "t")
    types = {c["name"]: c["type"] for c in schema["columns"]}
    assert types == {"id": "integer", "label": "text", "amount": "real"}


def test_table_schema_unknown_table(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    with pytest.raises(ValueError, match="Unknown table"):
        data.table_schema(con, "nope")


def test_get_table_pagination(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    page1 = data.get_table(con, "raw_widgets", limit=2, offset=0)
    page2 = data.get_table(con, "raw_widgets", limit=2, offset=2)
    assert [r["widget_id"] for r in page1] == ["W-1", "W-2"]
    assert [r["widget_id"] for r in page2] == ["W-3"]


def test_run_query_select(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    rows = data.run_query(con, "SELECT widget_id FROM raw_widgets WHERE price > 5 ORDER BY widget_id")
    assert [r["widget_id"] for r in rows] == ["W-1", "W-2"]


def test_run_query_rejects_non_select(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    with pytest.raises(ValueError, match="Only SELECT/WITH"):
        data.run_query(con, "DELETE FROM raw_widgets")


def test_run_query_write_fails_at_connection_layer(data_dir):
    """Even if a query slipped past the SELECT/WITH check, the connection itself is read-only."""
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    with pytest.raises(sqlite3.OperationalError):
        con.execute("INSERT INTO raw_widgets VALUES ('W-4', 'Sneaky', 1.0)")


def test_run_query_caps_limit(data_dir):
    con = data.connect_ro(data.resolve_db(data_dir, "widgets"))
    rows = data.run_query(con, "SELECT * FROM raw_widgets", limit=1)
    assert len(rows) == 1
