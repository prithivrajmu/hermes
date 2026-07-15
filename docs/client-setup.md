# MCP Client Setup (Claude Desktop)

Claude Desktop acts as the MCP client. maia serves over Streamable HTTP, and
Claude Desktop's config only launches servers over stdio, so the
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge sits in
between:

```
Claude Desktop ──(stdio)──▶ mcp-remote ──(Streamable HTTP)──▶ maia
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (for zeus/maia)
- [Node.js](https://nodejs.org/) (`npx` runs the `mcp-remote` bridge and MCP Inspector)
- [Claude Desktop](https://claude.ai/download) installed

## Step 1 — Generate data

maia serves whatever zeus has written to its output directory. Generate at
least one use case first:

```bash
cd zeus
uv sync
uv run zeus generate patient_history -n 500 --seed 42 -f sqlite   # → output/patient_history/patient_history.db
uv run zeus generate pharma_sales -n 20000 --seed 42 -f sqlite    # → output/pharma_sales/pharma_sales.db
```

Prefer a form over CLI flags? Install the optional UI extra and use the same
generation path through a browser:

```bash
uv sync --extra ui
uv run zeus ui   # → http://127.0.0.1:8501
```

## Step 2 — Start maia

```bash
cd maia
uv sync
uv run maia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
```

`--data-dir` scans `<data_dir>/<use_case>/<use_case>.db` and **re-scans on
every call** — generate more datasets later and they show up immediately,
no need to restart maia.

## Step 3 — What the tools are, and why

maia exposes five tools and one resource template. Each covers a distinct
access pattern an LLM client needs, from "what exists" down to "run
arbitrary SQL":

| Tool | Params | Returns | Description |
|---|---|---|---|
| `list_datasets()` | — | `[{dataset, tables: [{table, row_count}]}]` | Lists datasets and their tables. |
| `list_tables(dataset)` | `dataset: str` | `[{table, row_count}]` | Tables and row counts for a dataset. |
| `describe_table(dataset, table)` | `dataset, table: str` | `{table, columns: [{name, type}], sample_row}` | Columns (with inferred type) plus one sample row. |
| `get_table(dataset, table, limit=100, offset=0)` | + `limit, offset: int` (limit capped at 1000) | `[{...row}, ...]` | Paginated raw rows, no SQL required. |
| `query(dataset, sql, limit=200)` | `sql: str`, `limit: int` (capped at 5000) | `[{...row}, ...]` | Arbitrary read-only SQL (`SELECT`/`WITH` only). Read-only is enforced twice: a prefix check, and the sqlite connection itself is opened `mode=ro`. |
| resource `maia://{dataset}/schema` | — | Full table/column listing for a dataset, as JSON | Same information as `describe_table`, exposed as a resource instead of a tool call. |

### Example prompts to try in Claude Desktop

Once maia is connected, these exercise the tools above in a natural order:

- "What datasets are available?" → `list_datasets`
- "What tables are in patient_history?" → `list_tables`
- "Describe the raw_claims table" → `describe_table`
- "Show me 10 rows from raw_sales" → `get_table`
- "What are the top 5 brands by sales volume in pharma_sales?" → `query`

Two more using the `pharma_sales` dataset specifically:

- **Direct table pull**: "Show me 10 rows from raw_products in pharma_sales."
  → `get_table(dataset="pharma_sales", table="raw_products")`
- **Cross-table reasoning**: "In pharma_sales, which therapeutic area had the
  highest total gross revenue in 2023, broken down by region?" → joins
  `raw_sales`, `raw_products`, and `raw_countries` via `query`.

## Step 4 — Verify with MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) talks MCP
directly, with no LLM client (and no `mcp-remote` bridge) in between.
`maia serve` must already be running (Step 2).

### Interactive UI

```bash
npx @modelcontextprotocol/inspector
```

This opens a browser UI (`http://localhost:6274` by default). Set:

- **Transport Type**: `Streamable HTTP`
- **URL**: `http://127.0.0.1:8000/mcp`

then click **Connect**. From there you can browse maia's five tools and the
`maia://{dataset}/schema` resource, fill in arguments through a form, and
inspect the raw request/response JSON for each call.

### CLI mode (scriptable, no browser)

```bash
# List all tools and their schemas
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp \
  --method tools/list

# list_datasets — discovery entry point
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp \
  --method tools/call --tool-name list_datasets

# describe_table — columns + one sample row
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp \
  --method tools/call --tool-name describe_table \
  --tool-arg dataset=pharma_sales --tool-arg table=raw_sales

# query — arbitrary read-only SQL
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp \
  --method tools/call --tool-name query \
  --tool-arg dataset=pharma_sales \
  --tool-arg "sql=SELECT brand_name, SUM(units_sold) AS total_units FROM raw_sales GROUP BY brand_name ORDER BY total_units DESC LIMIT 5"

# Read the schema resource for a dataset
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp \
  --method resources/read --uri "maia://pharma_sales/schema"
```

CLI mode works well for scripting a smoke test against the server.

## Step 5 — Add maia to Claude Desktop

Open Claude Desktop's config file and add a `maia` entry under `mcpServers`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "maia": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://127.0.0.1:8000/mcp"]
    }
  }
}
```

If maia is running on a different host/port, change the URL to match.

## Step 6 — Restart & verify

Start `maia serve` first (Step 2), then restart Claude Desktop. Open the
tools/connectors view and confirm `maia` is listed with its five tools
(`list_datasets`, `list_tables`, `describe_table`, `get_table`, `query`).
Try one of the example prompts above to confirm it can actually reach data.

## Troubleshooting

- **Claude Desktop shows maia as disconnected / tools don't appear** — `maia serve`
  must already be running before Claude Desktop starts the `mcp-remote`
  bridge; the bridge doesn't retry a refused connection. Start maia first,
  then restart Claude Desktop.
- **Port already in use** — pick a different `--port` for `maia serve` and
  update the URL in the config to match.
- **`npx: command not found`** — Node.js isn't installed on the machine
  running Claude Desktop; install it from nodejs.org.
- **`mcp-remote` seems to be running a stale version** — `npx -y` re-resolves
  the package each run, but if you suspect a bad cache, clear it with
  `npx clear-npx-cache` and try again.
- **MCP Inspector can't connect** — same root cause as above: `maia serve`
  must be running first. Double check the URL includes the `/mcp` path
  (`http://127.0.0.1:8000/mcp`, not just the bare host:port) and that the
  Transport Type is set to `Streamable HTTP`, not `SSE`.
