"""ASGI app for the HTTP transports: MCP app plus an unauthenticated ``/health``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from starlette.requests import Request


async def health(request: Request) -> JSONResponse:
    """Liveness probe for Docker/Compose; touches neither auth, pgvector nor Ollama."""
    return JSONResponse({"status": "ok"})


def create_app(mcp: FastMCP, transport: Literal["http", "sse"] = "http") -> Starlette:
    """Wrap the MCP HTTP app in Starlette, adding ``/health``.

    ``lifespan`` of the MCP app MUST be passed on, otherwise every authorised request
    crashes with ``RuntimeError: Task group is not initialized``.

    Args:
        mcp: Configured server (auth already attached).
        transport: ``"http"`` (Streamable HTTP, path ``/mcp``) or ``"sse"``.

    Returns:
        The Starlette application to hand to uvicorn.
    """
    mcp_app = mcp.http_app(transport=transport)
    return Starlette(
        lifespan=mcp_app.lifespan,
        routes=[Route("/health", health), Mount("/", app=mcp_app)],
    )
