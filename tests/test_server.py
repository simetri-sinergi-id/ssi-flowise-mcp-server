"""Unit tests for settings, server factory, and _slugify."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from flowise_mcp_server.server import _slugify, build_server
from flowise_mcp_server.settings import Settings, ToolConfig

BASE_URL = "http://flowise.test"
API_KEY = "test-api-key"


# ── ToolConfig validation ────────────────────────────────────────────────────

def test_tool_config_valid() -> None:
    t = ToolConfig(id="uuid-1", name="search_wiki", description="Search docs")
    assert t.id == "uuid-1"
    assert t.name == "search_wiki"
    assert t.description == "Search docs"


def test_tool_config_default_description() -> None:
    t = ToolConfig(id="abcd1234-5678", name="my_tool")
    assert "abcd1234" in t.description


def test_tool_config_invalid_name_raises() -> None:
    with pytest.raises(ValueError, match="valid identifier"):
        ToolConfig(id="uuid", name="bad-name!")


# ── Settings.get_tools ───────────────────────────────────────────────────────

def test_get_tools_parses_json() -> None:
    s = Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_tools=json.dumps([
            {"id": "id-1", "name": "tool_a", "description": "Tool A"},
            {"id": "id-2", "name": "tool_b"},
        ]),
    )
    tools = s.get_tools()
    assert len(tools) == 2
    assert tools[0].name == "tool_a"
    assert tools[1].description  # auto-filled default


def test_get_tools_empty_when_not_set() -> None:
    s = Settings(flowise_base_url=BASE_URL, flowise_api_key=API_KEY)
    assert s.get_tools() == []


def test_get_tools_raises_on_invalid_json() -> None:
    s = Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_tools="not json",
    )
    with pytest.raises(ValueError, match="not valid JSON"):
        s.get_tools()


def test_get_tools_raises_missing_keys() -> None:
    s = Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_tools=json.dumps([{"id": "x"}]),  # missing "name"
    )
    with pytest.raises(ValueError, match="'id' and 'name'"):
        s.get_tools()


def test_settings_strips_trailing_slash() -> None:
    s = Settings(flowise_base_url=f"{BASE_URL}/", flowise_api_key=API_KEY)
    assert not s.flowise_base_url.endswith("/")


def test_settings_invalid_log_level() -> None:
    with pytest.raises(Exception):
        Settings(flowise_base_url=BASE_URL, flowise_api_key=API_KEY, mcp_log_level="VERBOSE")


def test_settings_invalid_transport() -> None:
    with pytest.raises(Exception):
        Settings(flowise_base_url=BASE_URL, flowise_api_key=API_KEY, mcp_transport="grpc")


# ── _slugify ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Wiki RAG", "wiki_rag"),
        ("FAQ Bot v2", "faq_bot_v2"),
        ("123flow", "flow_123flow"),
        ("hello--world", "hello_world"),
        ("  spaces  ", "spaces"),
        ("", "chatflow"),
        ("a", "a"),
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert _slugify(name) == expected


# ── build_server (explicit tools) ────────────────────────────────────────────

async def test_build_server_registers_explicit_tools() -> None:
    s = Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_tools=json.dumps([
            {"id": "ccc", "name": "my_tool", "description": "My tool"},
        ]),
    )
    mcp = await build_server(s)
    # FastMCP exposes registered tools; check via internal dict or list
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "my_tool" in tool_names


# ── build_server (auto-discover) ─────────────────────────────────────────────

@respx.mock
async def test_build_server_auto_discover() -> None:
    respx.get(f"{BASE_URL}/api/v1/chatflows").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "ddd", "name": "Wiki Search"},
                {"id": "eee", "name": "HR Bot"},
            ],
        )
    )
    s = Settings(
        flowise_base_url=BASE_URL,
        flowise_api_key=API_KEY,
        flowise_auto_discover=True,
    )
    mcp = await build_server(s)
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    assert "wiki_search" in tool_names
    assert "hr_bot" in tool_names


async def test_build_server_no_config_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    s = Settings(flowise_base_url=BASE_URL, flowise_api_key=API_KEY)
    import logging
    with caplog.at_level(logging.WARNING, logger="flowise_mcp_server.server"):
        await build_server(s)
    assert any("No tools configured" in r.message for r in caplog.records)
