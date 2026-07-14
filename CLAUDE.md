# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo structure

Hermes is a monorepo wrapping an end-to-end MCP (Model Context Protocol) stack, built in three stages. `zeus/` and `zaia/` are **git submodules** backed by their own standalone repos (`prithivrajmu/zeus`, `prithivrajmu/zaia`) — commits inside those directories belong to the submodule's own history, not hermes'. After cloning fresh, run `git submodule update --init --recursive` if the clone didn't use `--recurse-submodules`.

| # | Dir | Purpose | Status |
|---|-----|---------|--------|
| 1 | `zeus/` | Synthetic data generator producing raw source tables (with referential integrity + deliberate messy rows) for use cases like `patient_history` and `pharma_sales`, meant as ETL/ELT pipeline input. | done |
| 2 | `zaia/` | MCP server exposing zeus-generated sqlite datasets as MCP tools/resources over Streamable HTTP. | done |
| 3 | MCP client | Claude Desktop, via the `mcp-remote` bridge (no custom code) — see `docs/client-setup.md`. | planned |

Data flow: `zeus generate` → sqlite db per use case in `zeus/output/<use_case>/<use_case>.db` → `zaia serve --data-dir` scans that tree → MCP tools/resources over Streamable HTTP → `mcp-remote` bridge (stdio↔HTTP) → Claude Desktop.

Each submodule has its own README with full details; this file covers cross-cutting architecture and commands.

## Commands

Both submodules use `pyproject.toml` + hatchling and are installed independently:

```bash
cd zeus && pip install -e .
cd zaia && pip install -e .
```

Run tests (plain pytest, no config file — per-package):

```bash
cd zeus && pytest
cd zaia && pytest
pytest tests/test_framework.py::test_patient_history_referential_integrity   # single test
```

Generate data, then serve it:

```bash
cd zeus && zeus list
zeus generate patient_history -n 500 --seed 42 -f sqlite    # → output/patient_history/patient_history.db
zeus generate pharma_sales -n 20000 --seed 42 -f sqlite     # → output/pharma_sales/pharma_sales.db

cd ../zaia && zaia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
```

`zaia`'s `--data-dir` defaults to `$ZAIA_DATA_DIR` or `./output`, and re-scans on every call — no restart needed after generating new datasets.

## zeus architecture (synthetic data generator)

- `core/base.py` — `BaseGenerator` (abstract) + `GeneratorConfig` (count, seed, locale, free-form `options` dict). Subclasses set `name`/`description` and implement either `generate()` (single-table, yields dict records) or `generate_tables()` (multi-table, returns `{table_name: [records]}` with consistent foreign keys across tables). `self.rng` and `self.faker` are seeded together for determinism; `self.opt(key, default)` reads CLI `-o key=value` options.
- `core/registry.py` — `@register` decorator self-registers generator classes into a module-level dict keyed by `name`; `get(name)` looks them up. New use cases must be imported in `generators/__init__.py` to trigger registration (import has side effects — this is not optional).
- `core/writer.py` — output writers for json/jsonl/csv/sqlite.
- `generators/` — one module per use case. `example.py` is the single-table template; `patient_history.py` and `pharma_sales.py` model the multi-table raw-source pattern with FK integrity and ~1% injected messy rows (disable via `-o clean=true`).
- To add a use case: copy the closest template, give it a unique `name`, implement `generate()` or `generate_tables()`, and import the module in `generators/__init__.py`.

## zaia architecture (MCP server)

- `data.py` — no MCP dependency; pure dataset discovery + read-only sqlite access, kept separate specifically so it's testable in isolation from the MCP layer. `discover_datasets()` scans `<data_dir>/*/*.db` (one subdirectory = one dataset, named after the subdirectory). All connections open with `mode=ro` in the sqlite URI, so writes fail at the DB layer even if the SQL-prefix check in `run_query()` were bypassed — read-only is enforced at two independent layers, not just query text validation.
- `server.py` — `FastMCP` instance wiring `data.py` functions to five tools (`list_datasets`, `list_tables`, `describe_table`, `get_table`, `query`) and one resource template (`zaia://{dataset}/schema`). `configure(data_dir)` must be called once before `run()` (done by `cli.py`); `query()` only permits `SELECT`/`WITH` statements.
- `cli.py` — typer CLI, single `zaia serve` command.

When adding a new MCP tool, add the logic to `data.py` first (with a unit test that has no MCP dependency), then wire a thin tool wrapper in `server.py`.
