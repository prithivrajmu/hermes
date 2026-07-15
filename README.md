# Hermes

Monorepo for an end-to-end MCP (Model Context Protocol) stack, built in three major stages.
`zeus/` and `maia/` are git submodules backed by their own standalone repos
([`prithivrajmu/zeus`](https://github.com/prithivrajmu/zeus),
[`prithivrajmu/maia`](https://github.com/prithivrajmu/zaia) — repo rename pending, see below).

### Why "Hermes"?

In Greek mythology, Hermes — messenger of the gods — is the son of Zeus and Maia.
Here, `zeus/` generates the raw data and `maia/` serves it over MCP; `hermes` is the
messenger that ties the two together and carries the data through to the client.
The name isn't decoration — it's the architecture.

## Getting Started

```bash
git clone --recurse-submodules https://github.com/prithivrajmu/hermes.git
```

Already cloned without that flag? Run `git submodule update --init --recursive`.

Both submodules use [uv](https://docs.astral.sh/uv/); see their READMEs for setup.

## The Three Builds

| # | Sub-repo | Purpose |
|---|----------|---------|
| 1 | [`zeus/`](./zeus) | Synthetic data generator. Produces raw source tables for two use cases — patient history at a US insurance firm and pharma brand sales across countries — with referential integrity and deliberate messy rows, ready for an ETL/ELT pipeline to build mart tables. Extensible: new use cases plug in as generator modules. |
| 2 | [`maia/`](./maia) | MCP server. Exposes the zeus-generated datasets through MCP tools/resources so an LLM client can query them. Serves over Streamable HTTP. |
| 3 | MCP client | **Claude Desktop** acts as the client (no code needed — just a `claude_desktop_config.json` entry pointing at maia). See [`docs/client-setup.md`](./docs/client-setup.md) for the full walkthrough. |

## Repo Layout

```
hermes/
├── LICENSE          # Apache 2.0
├── README.md
├── .gitmodules
├── docs/            # Client setup guides
├── zeus/            # git submodule → prithivrajmu/zeus (Build 1 — data generation)
└── maia/            # git submodule → prithivrajmu/zaia (Build 2 — MCP server, repo rename pending)
```

## Flow

```
zeus (generate) ──▶ datasets (json / jsonl / csv / sqlite)
                        │
                        ▼
maia (MCP server, Streamable HTTP) ──▶ mcp-remote bridge ──▶ Claude Desktop (MCP client)
```

## License

Apache License 2.0 — see [LICENSE](./LICENSE).
