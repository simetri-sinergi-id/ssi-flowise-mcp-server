"""CLI entry point: configure logging, build the server, and run it."""

from __future__ import annotations

import asyncio
import logging
import sys

from .server import build_server
from .settings import Settings


def main() -> None:
    """Parse settings from the environment and start the MCP server."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:  # pydantic ValidationError or similar
        # Print a friendly message before the stack trace
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(
        level=settings.mcp_log_level.upper(),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    logger.info(
        "Starting flowise-mcp-server  transport=%s  host=%s  port=%s",
        settings.mcp_transport,
        settings.mcp_host,
        settings.mcp_port,
    )

    # build_server is async (may call Flowise for auto-discover)
    mcp = asyncio.run(build_server(settings))

    # mcp.run() starts its own event loop via uvicorn (streamable-http / sse)
    # or reads from stdin (stdio).
    mcp.run(
        transport=settings.mcp_transport,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
