"""Read-only access to zeus-generated sqlite datasets.

zeus writes one sqlite db per use case at ``<data_dir>/<use_case>/<use_case>.db``
(see ``zeus.core.writer.write_tables``). This module discovers those datasets
and provides read-only query access. It has no MCP dependency, so it's easy
to unit test in isolation from the server layer.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_READ_ONLY_PREFIXES = ("select", "with")


def discover_datasets(data_dir: Path) -> dict[str, Path]:
    """Map dataset name -> sqlite db path, scanning ``data_dir/*/*.db``."""
    if not data_dir.is_dir():
        return {}
    found: dict[str, Path] = {}
    for sub in sorted(data_dir.iterdir()):
        if not sub.is_dir():
            continue
        dbs = sorted(sub.glob("*.db"))
        if dbs:
            found[sub.name] = dbs[0]
    return found


def resolve_db(data_dir: Path, dataset: str) -> Path:
    datasets = discover_datasets(data_dir)
    try:
        return datasets[dataset]
    except KeyError:
        available = ", ".join(sorted(datasets)) or "<none>"
        raise ValueError(f"Unknown dataset {dataset!r}. Available: {available}") from None


def connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open a strictly read-only connection — writes fail at the DB layer
    regardless of what SQL text a caller passes to :func:`run_query`."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def list_tables(con: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    names = [row["name"] for row in cur.fetchall()]
    return [
        {"table": t, "row_count": con.execute(f'SELECT COUNT(*) AS n FROM "{t}"').fetchone()["n"]}
        for t in names
    ]


def resolve_table(con: sqlite3.Connection, table: str) -> str:
    names = {row["table"] for row in list_tables(con)}
    if table not in names:
        available = ", ".join(sorted(names)) or "<none>"
        raise ValueError(f"Unknown table {table!r}. Available: {available}")
    return table


def _infer_type(value: Any) -> str:
    """SQLite is dynamically typed and zeus's writer declares no column
    types, so PRAGMA table_info's type is always blank — infer from a
    sample value instead (same coarse categories SQLite itself uses)."""
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "integer"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    if isinstance(value, bytes):
        return "blob"
    return "text"


def table_schema(con: sqlite3.Connection, table: str) -> dict[str, Any]:
    table = resolve_table(con, table)
    cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    sample = con.execute(f'SELECT * FROM "{table}" LIMIT 1').fetchone()
    sample_dict = dict(sample) if sample else {}
    columns = [
        {"name": c["name"], "type": c["type"] or _infer_type(sample_dict.get(c["name"]))} for c in cols
    ]
    return {
        "table": table,
        "columns": columns,
        "sample_row": dict(sample) if sample else None,
    }


def get_table(con: sqlite3.Connection, table: str, limit: int = 100, offset: int = 0) -> list[dict]:
    table = resolve_table(con, table)
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    rows = con.execute(f'SELECT * FROM "{table}" LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return [dict(r) for r in rows]


def run_query(con: sqlite3.Connection, sql: str, limit: int = 200) -> list[dict]:
    stripped = sql.strip()
    first_word = stripped.split(None, 1)[0].lower() if stripped else ""
    if first_word not in _READ_ONLY_PREFIXES:
        raise ValueError(f"Only SELECT/WITH statements are allowed (got {first_word or '<empty>'!r})")
    limit = max(1, min(limit, 5000))
    rows = con.execute(stripped).fetchmany(limit)
    return [dict(r) for r in rows]
