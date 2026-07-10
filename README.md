# Hermes

Monorepo for an end-to-end MCP (Model Context Protocol) stack, built in three major stages.

## The Three Builds

| # | Sub-repo | Purpose | Status |
|---|----------|---------|--------|
| 1 | [`zeus/`](./zeus) | Synthetic data generator. Produces raw source tables for two use cases — **patient history at a US insurance firm** and **pharma brand sales across countries** — with referential integrity and deliberate messy rows, ready for an ETL/ELT pipeline to build mart tables. Extensible: new use cases plug in as generator modules. | ✅ v0.1 |
| 2 | [`zaia/`](./zaia) | MCP server. Exposes the zeus-generated datasets through MCP tools/resources so an LLM client can query them. | ⬜ Planned |
| 3 | MCP client | Initially **Claude Desktop** acts as the client (no code needed — just a `claude_desktop_config.json` entry pointing at zaia). A custom client may follow later. | ⬜ Planned |

## Repo Layout

```
hermes/
├── LICENSE          # Apache 2.0
├── README.md
├── docs/            # Architecture notes, client setup guides
├── zeus/            # Build 1 — data generation
└── zaia/            # Build 2 — MCP server
```

## Flow

```
zeus (generate) ──▶ datasets (json / jsonl / csv / sqlite)
                        │
                        ▼
zaia (MCP server) ──▶ Claude Desktop (MCP client)
```

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
