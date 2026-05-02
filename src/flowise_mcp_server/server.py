"""FastMCP server factory: registers Flowise chatflows as MCP tools."""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .client import FlowiseClient
from .settings import Settings, ToolConfig

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert an arbitrary string into a valid Python-style tool identifier."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9_]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if slug and slug[0].isdigit():
        slug = f"flow_{slug}"
    return slug or "chatflow"


def _register_tool(mcp: FastMCP, client: FlowiseClient, tool: ToolConfig) -> None:
    """Attach a single Flowise chatflow as an MCP tool on *mcp*."""
    # Capture tool.id in a local variable so each closure is independent.
    chatflow_id = tool.id

    @mcp.tool(name=tool.name, description=tool.description)
    async def _chatflow_query(
        query: Annotated[
            str,
            Field(description="The question or query to send to the chatflow"),
        ],
    ) -> str:
        return await client.predict(chatflow_id, query)

    logger.info("Registered MCP tool %r → chatflow %s", tool.name, tool.id)


async def build_server(settings: Settings) -> FastMCP:
    """Create a fully configured :class:`FastMCP` server.

    If ``FLOWISE_TOOLS`` is set, the listed chatflows are registered as tools.
    If ``FLOWISE_AUTO_DISCOVER`` is true (and ``FLOWISE_TOOLS`` is empty), all
    chatflows returned by the Flowise API are registered automatically.

    Args:
        settings: Validated application settings.

    Returns:
        A ready-to-run :class:`FastMCP` instance.
    """
    mcp = FastMCP(
        name="flowise-mcp-server",
        instructions=(
            "This server exposes Flowise chatflows as callable tools. "
            "Each tool accepts a natural-language query and returns the chatflow's response."
        ),
    )

    client = FlowiseClient(
        base_url=settings.flowise_base_url,
        api_key=settings.flowise_api_key,
        timeout=settings.flowise_timeout,
    )

    explicit_tools = settings.get_tools()

    if explicit_tools:
        for tool in explicit_tools:
            _register_tool(mcp, client, tool)

    elif settings.flowise_auto_discover:
        logger.info("Auto-discovering chatflows from %s …", settings.flowise_base_url)
        chatflows = await client.list_chatflows()
        logger.info("Discovered %d chatflow(s)", len(chatflows))
        for flow in chatflows:
            flow_id: str = flow.get("id", "")
            flow_name: str = flow.get("name", flow_id[:8])
            tool = ToolConfig(
                id=flow_id,
                name=_slugify(flow_name),
                description=f"Query Flowise chatflow: {flow_name}",
            )
            _register_tool(mcp, client, tool)

    else:
        logger.warning(
            "No tools configured. Set FLOWISE_TOOLS or FLOWISE_AUTO_DISCOVER=true."
        )

    return mcp
