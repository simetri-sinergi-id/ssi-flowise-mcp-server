"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from flowise_mcp_server.client import FlowiseClient
from flowise_mcp_server.settings import Settings


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
