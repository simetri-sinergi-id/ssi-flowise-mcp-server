"""Unit tests for the Wiki.js GraphQL client (fetch_wiki_page)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from flowise_mcp_server.settings import Settings
from flowise_mcp_server.wikijs import _normalise, fetch_page

GRAPHQL_URL = "http://wiki.test/graphql"
API_KEY = "test-wikijs-key"
DEFAULT_LOCALE = "id"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        flowise_base_url="http://flowise.test",
        flowise_api_key="test-api-key",
        wikijs_graphql_url=GRAPHQL_URL,
        wikijs_api_key=API_KEY,
        wikijs_locale=DEFAULT_LOCALE,
    )


def _page_response(path: str = "master-data/lokasi") -> dict:
    return {
        "data": {
            "pages": {
                "singleByPath": {
                    "id": 1,
                    "title": "Lokasi",
                    "description": "Master data lokasi",
                    "path": path,
                    "content": "# Isi halaman",
                    "updatedAt": "2026-07-01T00:00:00Z",
                }
            }
        }
    }


def _null_response() -> dict:
    return {"data": {"pages": {"singleByPath": None}}}


def _error_response(message: str = "Not authorized") -> dict:
    return {"errors": [{"message": message}]}


# ── _normalise ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("path", "default_locale", "expected"),
    [
        ("/en/a/b", "id", ("a/b", "en")),
        ("/a/b", "id", ("a/b", "id")),
        ("https://wiki.x/en/a/b?x=1", "id", ("a/b", "en")),
        ("a/b%20c", "id", ("a/b c", "id")),
    ],
)
def test_normalise(path: str, default_locale: str, expected: tuple[str, str]) -> None:
    assert _normalise(path, default_locale) == expected


# ── fetch_page ────────────────────────────────────────────────────────────────

@respx.mock
async def test_fetch_page_success_with_locale_prefix(settings: Settings) -> None:
    route = respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_page_response())
    )
    result = await fetch_page(settings, "/en/master-data/lokasi")

    assert route.call_count == 1
    body = json.loads(route.calls[0].request.content)
    assert body["variables"] == {"path": "master-data/lokasi", "locale": "en"}
    assert "Lokasi" in result
    assert "Path:" in result
    assert "Isi halaman" in result


@respx.mock
async def test_fetch_page_fallback_retries_with_prefixed_path(settings: Settings) -> None:
    route = respx.post(GRAPHQL_URL).mock(
        side_effect=[
            httpx.Response(200, json=_null_response()),
            httpx.Response(200, json=_page_response("en/master-data/lokasi")),
        ]
    )
    result = await fetch_page(settings, "/en/master-data/lokasi")

    assert route.call_count == 2
    second_body = json.loads(route.calls[1].request.content)
    assert second_body["variables"] == {
        "path": "en/master-data/lokasi",
        "locale": DEFAULT_LOCALE,
    }
    assert "Lokasi" in result


@respx.mock
async def test_fetch_page_not_found_after_fallback(settings: Settings) -> None:
    route = respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_null_response())
    )
    result = await fetch_page(settings, "/en/master-data/lokasi")

    assert route.call_count == 2
    assert "Page not found" in result
    assert "en/master-data/lokasi" in result
    assert DEFAULT_LOCALE in result


@respx.mock
async def test_fetch_page_bare_path_not_found_does_not_retry(settings: Settings) -> None:
    """A path with no locale-like prefix should not trigger a retry query."""
    route = respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_null_response())
    )
    result = await fetch_page(settings, "/master-data/lokasi")

    assert route.call_count == 1
    assert "Page not found" in result


@respx.mock
async def test_fetch_page_graphql_error(settings: Settings) -> None:
    route = respx.post(GRAPHQL_URL).mock(
        return_value=httpx.Response(200, json=_error_response("Not authorized"))
    )
    result = await fetch_page(settings, "/en/master-data/lokasi")

    assert route.call_count == 1
    assert "Not authorized" in result
    assert "Error fetching page" in result
