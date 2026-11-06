"""Front-door auth: API key, OAuth metadata, /health, fail-closed start-up."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from fastmcp.server.auth import MultiAuth
from mcp.server.auth.provider import TokenError
from pydantic import ValidationError
from starlette.testclient import TestClient

from flowise_mcp_server import cli
from flowise_mcp_server.asgi import create_app
from flowise_mcp_server.auth_provider import (
    AuthentikProvider,
    BearerApiKeyVerifier,
    build_auth,
)
from flowise_mcp_server.server import build_server
from flowise_mcp_server.settings import Settings

API_KEY = "s3cret-key-for-tests"
MCP_URL = "https://mcp.example.test"
OAUTH: dict[str, Any] = {
    "mcp_base_url": MCP_URL,
    "authentik_base_url": "https://auth.example.test",
    "authentik_app_slug": "flowise-mcp",
    "authentik_client_id": "cid",
    "authentik_client_secret": "csecret-0123456789",
}
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def _settings(**kw: Any) -> Settings:
    return Settings(flowise_base_url="http://flowise.test", flowise_api_key="k", **kw)


def _app(**kw: Any) -> Any:
    s = _settings(**kw)
    return create_app(asyncio.run(build_server(s)))


# ── API key ──────────────────────────────────────────────────────────────────


def test_post_mcp_without_token_is_401() -> None:
    with TestClient(_app(mcp_api_key=API_KEY)) as c:
        assert c.post("/mcp", json=INIT, headers=HEADERS).status_code == 401


def test_post_mcp_wrong_token_is_401() -> None:
    with TestClient(_app(mcp_api_key=API_KEY)) as c:
        h = {**HEADERS, "Authorization": "Bearer nope"}
        assert c.post("/mcp", json=INIT, headers=h).status_code == 401


def test_initialize_with_valid_bearer_passes_under_lifespan() -> None:
    with TestClient(_app(mcp_api_key=API_KEY)) as c:
        h = {**HEADERS, "Authorization": f"Bearer {API_KEY}"}
        resp = c.post("/mcp", json=INIT, headers=h)
    assert resp.status_code == 200, resp.text
    assert "Task group is not initialized" not in resp.text


def test_health_is_open_without_credentials() -> None:
    with TestClient(_app(mcp_api_key=API_KEY)) as c:
        resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_verifier_accepts_only_exact_key() -> None:
    v = BearerApiKeyVerifier(api_key=API_KEY)
    assert await v.verify_token(API_KEY) is not None
    assert await v.verify_token(API_KEY + "x") is None
    assert await v.verify_token("") is None


@pytest.mark.parametrize("bad", ["", "   "])
def test_blank_api_key_rejected_at_settings(bad: str) -> None:
    with pytest.raises(ValidationError):
        _settings(mcp_api_key=bad)


@pytest.mark.parametrize("bad", ["", "  "])
def test_blank_api_key_rejected_by_verifier(bad: str) -> None:
    with pytest.raises(ValueError):
        BearerApiKeyVerifier(api_key=bad)


# ── OAuth ────────────────────────────────────────────────────────────────────


def test_oauth_metadata_served_with_issuer() -> None:
    with TestClient(_app(**OAUTH)) as c:
        resp = c.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["issuer"].rstrip("/") == MCP_URL
    assert "registration_endpoint" in meta


def test_dynamic_client_registration_needs_no_client_id() -> None:
    with TestClient(_app(**OAUTH)) as c:
        meta = c.get("/.well-known/oauth-authorization-server").json()
        reg_path = "/" + meta["registration_endpoint"].split("/", 3)[3]
        resp = c.post(
            reg_path,
            json={
                "client_name": "claude",
                "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["client_id"]


def test_oauth_only_returns_provider_and_unauthenticated_post_is_401() -> None:
    assert isinstance(build_auth(_settings(**OAUTH)), AuthentikProvider)
    with TestClient(_app(**OAUTH)) as c:
        assert c.post("/mcp", json=INIT, headers=HEADERS).status_code == 401


def test_multiauth_when_oauth_and_api_key_both_active() -> None:
    assert isinstance(build_auth(_settings(mcp_api_key=API_KEY, **OAUTH)), MultiAuth)


def test_no_auth_returns_none() -> None:
    assert build_auth(_settings()) is None


@pytest.mark.parametrize("missing", list(OAUTH))
def test_partial_oauth_rejected(missing: str) -> None:
    partial = {k: v for k, v in OAUTH.items() if k != missing}
    with pytest.raises(ValidationError, match="incomplete"):
        _settings(**partial)


# ── TokenError codes ─────────────────────────────────────────────────────────

VALID_CODES = {
    "invalid_request",
    "invalid_client",
    "invalid_grant",
    "unauthorized_client",
    "unsupported_grant_type",
    "invalid_scope",
}


def _provider() -> AuthentikProvider:
    p = build_auth(_settings(**OAUTH))
    assert isinstance(p, AuthentikProvider)
    return p


async def test_token_error_missing_access_token_uses_valid_code() -> None:
    with pytest.raises(TokenError) as ei:
        await _provider()._extract_upstream_claims({})
    assert ei.value.error in VALID_CODES


async def test_token_error_userinfo_unreachable_uses_valid_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx
    import respx

    with respx.mock:
        respx.get("https://auth.example.test/application/o/userinfo/").mock(
            side_effect=httpx.ConnectError("down")
        )
        with pytest.raises(TokenError) as ei:
            await _provider()._extract_upstream_claims({"access_token": "t"})
    assert ei.value.error in VALID_CODES


async def test_token_error_userinfo_rejected_and_no_username_use_valid_codes() -> None:
    import httpx
    import respx

    url = "https://auth.example.test/application/o/userinfo/"
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(401))
        with pytest.raises(TokenError) as e1:
            await _provider()._extract_upstream_claims({"access_token": "t"})
        respx.get(url).mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(TokenError) as e2:
            await _provider()._extract_upstream_claims({"access_token": "t"})
    assert e1.value.error in VALID_CODES
    assert e2.value.error in VALID_CODES


async def test_userinfo_success_returns_claims() -> None:
    import httpx
    import respx

    with respx.mock:
        respx.get("https://auth.example.test/application/o/userinfo/").mock(
            return_value=httpx.Response(200, json={"preferred_username": "Andi", "sub": "1"})
        )
        claims = await _provider()._extract_upstream_claims({"access_token": "t"})
    assert claims is not None
    assert claims["username"] == "andi"


# ── Start-up policy (fail closed) ────────────────────────────────────────────


def _env(monkeypatch: pytest.MonkeyPatch, **kw: str) -> None:
    monkeypatch.setenv("FLOWISE_BASE_URL", "http://flowise.test")
    monkeypatch.setenv("FLOWISE_API_KEY", "k")
    for k, v in kw.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the real servers so ``main()`` returns; records what would have run."""
    calls: list[str] = []
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: calls.append("uvicorn"))
    from fastmcp import FastMCP

    monkeypatch.setattr(FastMCP, "run", lambda self, **kw: calls.append("stdio"))
    return calls


def test_http_without_auth_exits_1(
    monkeypatch: pytest.MonkeyPatch, served: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    _env(monkeypatch)
    with pytest.raises(SystemExit) as ei:
        cli.main()
    assert ei.value.code == 1
    assert "Configuration error" in capsys.readouterr().err
    assert served == []


def test_sse_without_auth_exits_1(monkeypatch: pytest.MonkeyPatch, served: list[str]) -> None:
    _env(monkeypatch, MCP_TRANSPORT="sse")
    with pytest.raises(SystemExit) as ei:
        cli.main()
    assert ei.value.code == 1


def test_allow_anonymous_starts_http(monkeypatch: pytest.MonkeyPatch, served: list[str]) -> None:
    _env(monkeypatch, MCP_ALLOW_ANONYMOUS="true")
    cli.main()
    assert served == ["uvicorn"]


def test_api_key_starts_http(monkeypatch: pytest.MonkeyPatch, served: list[str]) -> None:
    _env(monkeypatch, MCP_API_KEY=API_KEY)
    cli.main()
    assert served == ["uvicorn"]


def test_stdio_starts_without_auth(monkeypatch: pytest.MonkeyPatch, served: list[str]) -> None:
    _env(monkeypatch, MCP_TRANSPORT="stdio")
    cli.main()
    assert served == ["stdio"]


def test_partial_oauth_exits_1(monkeypatch: pytest.MonkeyPatch, served: list[str]) -> None:
    _env(monkeypatch, MCP_BASE_URL=MCP_URL, AUTHENTIK_CLIENT_ID="x")
    with pytest.raises(SystemExit) as ei:
        cli.main()
    assert ei.value.code == 1


def test_anonymous_start_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        _settings(mcp_allow_anonymous=True).check_auth_policy()
    assert any("WITHOUT auth" in r.message for r in caplog.records)
