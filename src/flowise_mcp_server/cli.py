"""CLI entry point: configure logging, build the server, and run it."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import uvicorn
from fastmcp import settings as fastmcp_settings

from .asgi import create_app
from .server import build_server
from .settings import Settings


def main() -> None:
    """Parse settings from the environment and start the MCP server."""
    try:
        settings = Settings()  # type: ignore[call-arg]
        settings.check_auth_policy()
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

    if settings.mcp_state_dir:
        # Where OAuthProxy persists client registrations (see README, "OAuth storage").
        fastmcp_settings.home = Path(settings.mcp_state_dir)

    # build_server is async (may call Flowise for auto-discover); it must run before
    # uvicorn starts because uvicorn loads the app inside its own event loop.
    try:
        mcp = asyncio.run(build_server(settings))
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    if settings.mcp_transport == "stdio":
        mcp.run(transport="stdio")
        return

    transport = "sse" if settings.mcp_transport == "sse" else "http"
    uvicorn.run(
        create_app(mcp, transport),
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=settings.mcp_log_level,
    )
