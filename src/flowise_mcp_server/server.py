"""FastMCP server factory: registers Flowise chatflows as MCP tools."""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .auth_provider import build_auth
from .client import FlowiseClient
from .retriever import retrieve
from .settings import Settings, ToolConfig
from .wikijs import fetch_page

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert an arbitrary string into a valid Python-style tool identifier."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9_]", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if slug and slug[0].isdigit():
        slug = f"flow_{slug}"
    return slug or "chatflow"


def _register_direct_tool(mcp: FastMCP, settings: Settings, tool: ToolConfig) -> None:
    """Register a tool that queries pgvector + Ollama directly (no Flowise prediction)."""

    @mcp.tool(name=tool.name, description=tool.description)
    async def _direct_query(
        query: Annotated[
            str,
            Field(description="The search query to find relevant documents"),
        ],
    ) -> str:
        return await retrieve(settings, query)

    logger.info(
        "Registered MCP tool %r → direct pgvector retrieval (table=%s)",
        tool.name,
        settings.pgvector_table,
    )


def _register_tool(mcp: FastMCP, client: FlowiseClient, tool: ToolConfig) -> None:
    """Attach a single Flowise chatflow as an MCP tool on *mcp*."""
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


def _register_wikijs_tool(mcp: FastMCP, settings: Settings) -> None:
    """Register the fetch_wiki_page tool for fetching full Wiki.js page content."""

    @mcp.tool(
        name="fetch_wiki_page",
        description=(
            "Fetch the full markdown content of a Wiki.js page by its path. "
            "Use this when you need the complete text of a specific page — for example "
            "when a search result contains a link like /master-data/lokasi/01-membuat "
            "and you need to read that page in full. "
            "Path examples: /master-data/lokasi, /instruksi-kerja/lokasi/01-membuat, "
            "/troubleshoot/stock/stok-tidak-berkurang. "
            "A locale prefix (e.g. /en/master-data/lokasi, as shown in search results and "
            "browser URLs) or a full URL is also accepted and handled automatically — do not "
            "strip the locale segment yourself before calling this tool."
        ),
    )
    async def _fetch_wiki_page(
        path: Annotated[
            str,
            Field(
                description=(
                    "Path of the Wiki.js page, e.g. /master-data/lokasi/01-membuat. "
                    "A locale prefix (/en/...) or a full page URL is also accepted."
                )
            ),
        ],
    ) -> str:
        return await fetch_page(settings, path)

    logger.info(
        "Registered MCP tool 'fetch_wiki_page' → Wiki.js GraphQL %s",
        settings.wikijs_graphql_url,
    )


async def build_server(settings: Settings) -> FastMCP:
    """Create a fully configured :class:`FastMCP` server.

    When ``PGVECTOR_HOST`` / ``OLLAMA_BASE_URL`` are set (direct mode), tools
    query pgvector + Ollama directly — no Flowise prediction API needed.

    Otherwise, chatflows listed in ``FLOWISE_TOOLS`` or discovered via
    ``FLOWISE_AUTO_DISCOVER`` are called through the Flowise prediction API.

    Args:
        settings: Validated application settings.

    Returns:
        A ready-to-run :class:`FastMCP` instance.
    """
    direct_mode = settings.is_direct_mode()
    if direct_mode:
        logger.info(
            "Direct retrieval mode: pgvector=%s/%s  ollama=%s  table=%s  top_k=%d",
            settings.pgvector_host,
            settings.pgvector_db,
            settings.ollama_base_url,
            settings.pgvector_table,
            settings.top_k,
        )

    mcp = FastMCP(
        name="flowise-mcp-server",
        auth=build_auth(settings),
        instructions=(
            "This server exposes Flowise chatflows as callable tools. "
            "Each tool accepts a natural-language query and returns the chatflow's response. "
            "When search results contain links to wiki pages, use fetch_wiki_page to retrieve "
            "the full content of those pages for complete context."
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
            if direct_mode:
                _register_direct_tool(mcp, settings, tool)
            else:
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
            if direct_mode:
                _register_direct_tool(mcp, settings, tool)
            else:
                _register_tool(mcp, client, tool)

    else:
        logger.warning(
            "No tools configured. Set FLOWISE_TOOLS or FLOWISE_AUTO_DISCOVER=true."
        )

    if settings.is_wikijs_configured():
        _register_wikijs_tool(mcp, settings)

    return mcp
