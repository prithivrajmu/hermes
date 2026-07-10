# Zaia

Build 2 of the Hermes stack: the **MCP server**.

Exposes the sqlite datasets produced by [zeus](../zeus) as MCP tools/resources,
so an MCP client (e.g. Claude Desktop) can explore and query them. Transport
is **Streamable HTTP** (the current MCP spec transport — SSE-only servers are
deprecated as of the 2025-03-26 revision).

## Install

```bash
cd zaia
pip install -e .
```

## Usage

Generate data with zeus first (see [`../zeus`](../zeus)), then point zaia at
its output directory:

```bash
cd zeus && zeus generate patient_history -n 500 --seed 42 -f sqlite
cd zeus && zeus generate pharma_sales -n 20000 --seed 42 -f sqlite

cd zaia && zaia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
```

`--data-dir` defaults to `$ZAIA_DATA_DIR` or `./output`. It scans
`<data_dir>/<use_case>/<use_case>.db` — each subdirectory with a `.db` file
becomes a queryable "dataset" — and re-scans on every call, so newly
generated datasets show up without restarting the server.

## Tools

| Tool | Purpose |
|---|---|
| `list_datasets()` | List datasets and their tables |
| `list_tables(dataset)` | Tables + row counts for a dataset |
| `describe_table(dataset, table)` | Columns (name + inferred type) + one sample row |
| `get_table(dataset, table, limit=100, offset=0)` | Paginated raw rows, no SQL needed |
| `query(dataset, sql, limit=200)` | Arbitrary read-only SQL (`SELECT`/`WITH` only) |

Also one resource template, `zaia://{dataset}/schema`, returning the full
table/column listing for a dataset as JSON.

All access is strictly read-only: the sqlite connection itself is opened in
`mode=ro`, so writes fail at the DB layer even if `query`'s SQL-prefix check
were somehow bypassed.

## Claude Desktop setup

Claude Desktop's `claude_desktop_config.json` launches MCP servers over
stdio, so an HTTP server needs a bridge — [`mcp-remote`](https://www.npmjs.com/package/mcp-remote)
does this:

```json
{
  "mcpServers": {
    "zaia": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:8000/mcp"]
    }
  }
}
```

Start `zaia serve` first, then restart Claude Desktop to pick up the config.
See [`../docs/client-setup.md`](../docs/client-setup.md) for details.

## Layout

```
zaia/
├── pyproject.toml
├── src/zaia/
│   ├── data.py      # dataset discovery + read-only sqlite access (no MCP dependency)
│   ├── server.py    # FastMCP instance: tools + resource
│   └── cli.py       # typer CLI: `zaia serve`
└── tests/
    └── test_data.py
```
