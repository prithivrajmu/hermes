"""zaia CLI.

    zaia serve --data-dir ../zeus/output --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from zaia.server import configure, mcp

app = typer.Typer(help="zaia — MCP server exposing zeus-generated datasets.", no_args_is_help=True)


@app.callback()
def _main() -> None:
    """zaia — MCP server exposing zeus-generated datasets."""


@app.command()
def serve(
    data_dir: Path = typer.Option(
        Path(os.environ.get("ZAIA_DATA_DIR", "output")),
        "--data-dir",
        help="Directory containing zeus sqlite output (<data_dir>/<use_case>/<use_case>.db). "
        "Defaults to $ZAIA_DATA_DIR or ./output.",
    ),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Start the MCP server over Streamable HTTP."""
    configure(data_dir)
    mcp.settings.host = host
    mcp.settings.port = port
    typer.echo(f"zaia serving datasets from {data_dir} at http://{host}:{port}{mcp.settings.streamable_http_path}")
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    app()
