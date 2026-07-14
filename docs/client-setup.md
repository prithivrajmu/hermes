# MCP Client Setup (Claude Desktop)

Build 3 uses Claude Desktop as the MCP client. zaia (build 2) serves over
**Streamable HTTP**, and Claude Desktop's config only launches servers over
stdio, so the [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge
sits in between:

```
Claude Desktop ──(stdio)──▶ mcp-remote ──(Streamable HTTP)──▶ zaia
```

This whole path — zaia serving, and `mcp-remote` bridging stdio to it — has
been verified working end-to-end with a real MCP client handshake (see
Step 4, which uses [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
to verify zaia directly, no Claude Desktop required). The one step that
can't be verified from a terminal is Claude Desktop's own UI picking up the
tools; that's the final manual check in Step 6.

## Prerequisites

- Python 3.10+ (for zeus/zaia)
- [Node.js](https://nodejs.org/) (`npx` runs the `mcp-remote` bridge and MCP Inspector)
- [Claude Desktop](https://claude.ai/download) installed

## Step 1 — Generate data

zaia serves whatever zeus has written to its output directory. Generate at
least one use case first:

```bash
cd zeus
pip install -e .
zeus generate patient_history -n 500 --seed 42 -f sqlite   # → output/patient_history/patient_history.db
zeus generate pharma_sales -n 20000 --seed 42 -f sqlite    # → output/pharma_sales/pharma_sales.db
```

Prefer a form over CLI flags? Install the optional UI extra and use the same
generation path through a browser:

```bash
pip install -e ".[ui]"
zeus ui   # → http://127.0.0.1:8501
```

## Step 2 — Start zaia

```bash
cd zaia
pip install -e .
zaia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
```

`--data-dir` scans `<data_dir>/<use_case>/<use_case>.db` and **re-scans on
every call** — generate more datasets later and they show up immediately,
no need to restart zaia.

## Step 3 — What the tools are, and why

zaia exposes five tools and one resource template. Each covers a distinct
access pattern an LLM client needs, from "what exists" down to "run
arbitrary SQL":

| Tool | Params | Returns | Why it exists |
|---|---|---|---|
| `list_datasets()` | — | `[{dataset, tables: [{table, row_count}]}]` | Discovery entry point. A client with zero prior context learns what datasets and tables exist without guessing names. Always call this first. |
| `list_tables(dataset)` | `dataset: str` | `[{table, row_count}]` | Scoped discovery once a dataset is picked — row counts let the model gauge size before deciding whether to page through it or query it directly. |
| `describe_table(dataset, table)` | `dataset, table: str` | `{table, columns: [{name, type}], sample_row}` | Columns (with inferred type) plus one real sample row, so the model isn't guessing column names or types before writing SQL. Call this before querying an unfamiliar table. |
| `get_table(dataset, table, limit=100, offset=0)` | + `limit, offset: int` (limit capped at 1000) | `[{...row}, ...]` | Cheap "just show me rows" path — paginated raw rows with no SQL required. |
| `query(dataset, sql, limit=200)` | `sql: str`, `limit: int` (capped at 5000) | `[{...row}, ...]` | Escape hatch for anything the structured tools above can't answer — arbitrary read-only SQL. Read-only is enforced twice: a `SELECT`/`WITH`-only prefix check, and the sqlite connection itself is opened `mode=ro`, so writes fail at the DB layer even if the prefix check were bypassed. |
| resource `zaia://{dataset}/schema` | — | Full table/column listing for a dataset, as JSON | Same information as `describe_table`, but as a browsable resource rather than a tool call — useful for clients that surface resources in a sidebar instead of invoking a tool. |

### Example prompts to try in Claude Desktop

Once zaia is connected, these exercise the tools above in a natural order:

- "What datasets are available?" → `list_datasets`
- "What tables are in patient_history?" → `list_tables`
- "Describe the raw_claims table" → `describe_table`
- "Show me 10 rows from raw_sales" → `get_table`
- "What are the top 5 brands by sales volume in pharma_sales?" → `query`

Two more using the `pharma_sales` dataset specifically — one that just pulls
rows straight from a table, and one that requires the model to reason across
tables:

- **Direct table pull**: "Show me 10 rows from raw_products in pharma_sales."
  This maps straight to `get_table(dataset="pharma_sales", table="raw_products")`
  — no SQL, no joins, just raw rows back.
- **Cross-table reasoning**: "In pharma_sales, which therapeutic area had the
  highest total gross revenue in 2023, broken down by region?" This can't be
  answered by one `get_table` call — the model has to `describe_table` its way
  across `raw_sales`, `raw_products` (for `therapeutic_area`), and
  `raw_countries` (for `region`), then write a `query` that joins and
  aggregates them.

## Step 4 — Verify with MCP Inspector

Before wiring zaia into Claude Desktop, it's worth confirming the server
itself actually works. [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
is the official dev tool for this — it talks MCP directly, with no LLM
client (and no `mcp-remote` bridge) in between, since Inspector supports
Streamable HTTP natively. `zaia serve` must already be running (Step 2).

### Interactive UI

```bash
npx @modelcontextprotocol/inspector
```

This opens a browser UI (`http://localhost:6274` by default). Set:

- **Transport Type**: `Streamable HTTP`
- **URL**: `http://127.0.0.1:8000/mcp`

then click **Connect**. From there you can browse zaia's five tools and the
`zaia://{dataset}/schema` resource, fill in arguments through a form, and
inspect the raw request/response JSON for each call.

### CLI mode (scriptable, no browser)

Every example below has been run against a live zaia instance:

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
  --method resources/read --uri "zaia://pharma_sales/schema"
```

CLI mode is the faster loop for iterating on `data.py`/`server.py` changes —
no need to click through a UI to check a tool's output shape, and it's easy
to script as a smoke test.

## Step 5 — Add zaia to Claude Desktop

Open Claude Desktop's config file and add a `zaia` entry under `mcpServers`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

If zaia is running on a different host/port, change the URL to match.

## Step 6 — Restart & verify

Start `zaia serve` first (Step 2), then restart Claude Desktop. Open the
tools/connectors view and confirm `zaia` is listed with its five tools
(`list_datasets`, `list_tables`, `describe_table`, `get_table`, `query`).
Try one of the example prompts above to confirm it can actually reach data.

## Troubleshooting

- **Claude Desktop shows zaia as disconnected / tools don't appear** — `zaia serve`
  must already be running before Claude Desktop starts the `mcp-remote`
  bridge; the bridge doesn't retry a refused connection. Start zaia first,
  then restart Claude Desktop.
- **Port already in use** — pick a different `--port` for `zaia serve` and
  update the URL in the config to match.
- **`npx: command not found`** — Node.js isn't installed on the machine
  running Claude Desktop; install it from nodejs.org.
- **`mcp-remote` seems to be running a stale version** — `npx -y` re-resolves
  the package each run, but if you suspect a bad cache, clear it with
  `npx clear-npx-cache` and try again.
- **MCP Inspector can't connect** — same root cause as above: `zaia serve`
  must be running first. Double check the URL includes the `/mcp` path
  (`http://127.0.0.1:8000/mcp`, not just the bare host:port) and that the
  Transport Type is set to `Streamable HTTP`, not `SSE`.
