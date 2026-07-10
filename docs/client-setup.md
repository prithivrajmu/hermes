# MCP Client Setup (Claude Desktop)

Build 3 uses Claude Desktop as the MCP client — no code, just configuration.
Once zaia exists, add it to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zaia": {
      "command": "<zaia launch command>",
      "args": []
    }
  }
}
```

Details to be filled in when zaia's transport (stdio vs HTTP) is decided.
