"""Shared pytest fixtures."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flowise_mcp_server.client import FlowiseClient
from flowise_mcp_server.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

BASE_URL = "http://flowise.test"
API_KEY = "test-api-key-1234"


@pytest.fixture
def settings_explicit() -> Settings:
    """Settings with two explicitly configured tools."""
    return Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_tools=(
            '[{"id": "aaaa-1111", "name": "search_wiki", "description": "Search Wiki.js"},'
            ' {"id": "bbbb-2222", "name": "search_faq", "description": "Search FAQ"}]'
        ),
    )


@pytest.fixture
def settings_auto_discover() -> Settings:
    """Settings with auto-discover enabled."""
    return Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_auto_discover=True,
    )


@pytest.fixture
def client() -> FlowiseClient:
    return FlowiseClient(base_url=BASE_URL, api_key=API_KEY, timeout=10)


@pytest.fixture(autouse=True)
def _isolate_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep OAuth storage in a temp dir and drop auth env that may leak from the host."""
    import fastmcp

    monkeypatch.setattr(fastmcp.settings, "home", tmp_path / "fastmcp-home")
    for name in (
        "MCP_BASE_URL",
        "AUTHENTIK_BASE_URL",
        "AUTHENTIK_APP_SLUG",
        "AUTHENTIK_CLIENT_ID",
        "AUTHENTIK_CLIENT_SECRET",
        "MCP_API_KEY",
        "MCP_ALLOW_ANONYMOUS",
        "MCP_STATE_DIR",
        "MCP_TRANSPORT",
    ):
        monkeypatch.delenv(name, raising=False)
