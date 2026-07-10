# MCP Client Setup (Claude Desktop)

Build 3 uses Claude Desktop as the MCP client. zaia (build 2) serves over
**Streamable HTTP**, and Claude Desktop's config only launches servers over
stdio, so the [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge
sits in between:

```
Claude Desktop ──(stdio)──▶ mcp-remote ──(Streamable HTTP)──▶ zaia
```

## Steps

1. Generate data and start zaia (see [`../zaia/README.md`](../zaia/README.md)):
   ```bash
   zaia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
   ```
2. Add zaia to `claude_desktop_config.json`:
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
3. Restart Claude Desktop. It should show `zaia`'s five tools
   (`list_datasets`, `list_tables`, `describe_table`, `get_table`, `query`)
   available to the model.

Requires Node.js (for `npx`) on the machine running Claude Desktop, in
addition to the zaia server itself running somewhere reachable.
