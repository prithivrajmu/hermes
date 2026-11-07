# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo structure

Hermes is a monorepo wrapping an end-to-end MCP (Model Context Protocol) stack, built in three stages. `zeus/`, `maia/` and `odysseus/` are **git submodules** backed by their own standalone repos (`prithivrajmu/zeus`, `prithivrajmu/zaia` — GitHub repo rename to `prithivrajmu/maia` pending) — commits inside those directories belong to the submodule's own history, not hermes'. After cloning fresh, run `git submodule update --init --recursive` if the clone didn't use `--recurse-submodules`.

| # | Dir | Purpose |
|---|-----|---------|
| 1 | `zeus/` | Synthetic data generator producing raw source tables (with referential integrity + deliberate messy rows) for use cases like `patient_history` and `pharma_sales`, meant as ETL/ELT pipeline input. |
| 2 | `maia/` | MCP server exposing zeus-generated sqlite datasets as MCP tools/resources over Streamable HTTP. |
| 3 | MCP client | Claude Desktop, via the `mcp-remote` bridge (no custom code) — see `docs/client-setup.md`. |

Data flow: `zeus generate` → sqlite db per use case in `zeus/output/<use_case>/<use_case>.db` → `maia serve --data-dir` scans that tree → MCP tools/resources over Streamable HTTP → `mcp-remote` bridge (stdio↔HTTP) → Claude Desktop.

`odysseus/` is a third **git submodule** (`prithivrajmu/odysseus`, branch `main`) — the ARGOS ELT pipeline (Snowflake Dynamic Tables) that consumes zeus output; see the odysseus section below. It is pointer-only: its CI, deploys and releases live in its own repo (hermes has no odysseus workflow), and commits go inside `odysseus/`, then a hermes commit bumps the pointer. Rationale: `odysseus/docs/07_repository.md`.

Each submodule has its own README with full details; this file covers cross-cutting architecture and commands.

## Commands

Both submodules use `pyproject.toml` + hatchling and are managed independently with [uv](https://docs.astral.sh/uv/):

```bash
cd zeus && uv sync
cd maia && uv sync
```

Run tests (plain pytest, no config file — per-package):

```bash
cd zeus && uv run pytest
cd maia && uv run pytest
uv run pytest tests/test_framework.py::test_patient_history_referential_integrity   # single test
```

Generate data, then serve it:

```bash
cd zeus && uv run zeus list
uv run zeus generate patient_history -n 500 --seed 42 -f sqlite    # → output/patient_history/patient_history.db
uv run zeus generate pharma_sales -n 20000 --seed 42 -f sqlite     # → output/pharma_sales/pharma_sales.db

cd ../maia && uv run maia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
```

`maia`'s `--data-dir` defaults to `$MAIA_DATA_DIR` or `./output`, and re-scans on every call — no restart needed after generating new datasets.

## zeus architecture (synthetic data generator)

- `core/base.py` — `BaseGenerator` (abstract) + `GeneratorConfig` (count, seed, locale, free-form `options` dict). Subclasses set `name`/`description` and implement either `generate()` (single-table, yields dict records) or `generate_tables()` (multi-table, returns `{table_name: [records]}` with consistent foreign keys across tables). `self.rng` and `self.faker` are seeded together for determinism; `self.opt(key, default)` reads CLI `-o key=value` options.
- `core/registry.py` — `@register` decorator self-registers generator classes into a module-level dict keyed by `name`; `get(name)` looks them up. New use cases must be imported in `generators/__init__.py` to trigger registration (import has side effects — this is not optional).
- `core/writer.py` — output writers for json/jsonl/csv/sqlite.
- `generators/` — one module per use case. `example.py` is the single-table template; `patient_history.py` and `pharma_sales.py` model the multi-table raw-source pattern with FK integrity and ~1% injected messy rows (disable via `-o clean=true`).
- To add a use case: copy the closest template, give it a unique `name`, implement `generate()` or `generate_tables()`, and import the module in `generators/__init__.py`.

## maia architecture (MCP server)

- `data.py` — no MCP dependency; pure dataset discovery + read-only sqlite access, kept separate specifically so it's testable in isolation from the MCP layer. `discover_datasets()` scans `<data_dir>/*/*.db` (one subdirectory = one dataset, named after the subdirectory). All connections open with `mode=ro` in the sqlite URI, so writes fail at the DB layer even if the SQL-prefix check in `run_query()` were bypassed — read-only is enforced at two independent layers, not just query text validation.
- `server.py` — `FastMCP` instance wiring `data.py` functions to five tools (`list_datasets`, `list_tables`, `describe_table`, `get_table`, `query`) and one resource template (`maia://{dataset}/schema`). `configure(data_dir)` must be called once before `run()` (done by `cli.py`); `query()` only permits `SELECT`/`WITH` statements.
- `cli.py` — typer CLI, single `maia serve` command.

When adding a new MCP tool, add the logic to `data.py` first (with a unit test that has no MCP dependency), then wire a thin tool wrapper in `server.py`.

## odysseus architecture (ARGOS ELT pipeline, standalone repo)

Pure Snowflake SQL — no dbt, no external orchestrator. Layers run in numbered-directory order under `sql/`: `00_setup` (platform, RAW tables, seeds) → `10_staging` (STG views) → `20_core` (dims/facts as Dynamic Tables) → `30_sem` (metric views) → `40_mart` (mart Dynamic Tables) → `50_serving` (`sp_generate_brand_views()` emits per-brand `SERVING.<brand>_<mart>` secure views). Dynamic Tables infer the refresh DAG from the tables they read; `TARGET_LAG` drives refresh.

- **Brand is a column, never a schema/table name.** Every fact leads with `brand_id`; onboarding a brand = a `seed_brand` row + re-run the serving proc, no new tables.
- Environment = database (`ARGOS_DEV/TEST/PROD`), passed to the SQL files as the `$argos_db` session variable (`IDENTIFIER($argos_db)`). Deploy with `cd odysseus && ./deploy.sh ARGOS_DEV [snow-connection]` (needs the Snowflake CLI `snow`; the RAW load step is commented out in `deploy.sh` until CSVs are staged).
- `contracts/` (JSON Schema → generated TS types, `@argos/contracts`) is the source of truth for the Next.js consumer. After editing `contracts/schemas/argos.schema.json`, run `npm run generate` in `contracts/` (`npm run check` fails on a stale `generated/`).

Tests (run from `odysseus/`): the same files run against two backends, picked by `ARGOS_TEST_BACKEND` (`duckdb` default, or `snowflake` + `SNOWFLAKE_*` creds). The DuckDB surrogate transpiles the Snowflake SQL with sqlglot over RAW data generated in-process by zeus (`brand1_aa` generator), so Snowflake-only syntax changes can break `surrogate.py` even when the SQL is valid.

```bash
cd odysseus && pip install -r tests/requirements-test.txt
python -m pytest tests -q
python -m pytest tests/test_serving_contract.py -q
```

CI lives only in `odysseus/.github/workflows/ci.yml` (the DuckDB job runs on every push/PR; the Snowflake job runs on `main` when `SNOWFLAKE_*` secrets exist). Env var is `ARGOS_TEST_BACKEND`.
