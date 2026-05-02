"""Unit tests for FlowiseClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from flowise_mcp_server.client import FlowiseClient

BASE_URL = "http://flowise.test"
API_KEY = "test-api-key"
CHATFLOW_ID = "test-chatflow-uuid-1234"


@pytest.fixture
def client() -> FlowiseClient:
    return FlowiseClient(base_url=BASE_URL, api_key=API_KEY, timeout=10)


# ── predict ─────────────────────────────────────────────────────────────────

@respx.mock
async def test_predict_returns_text_key(client: FlowiseClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(200, json={"text": "Hello from Flowise"})
    )
    result = await client.predict(CHATFLOW_ID, "hello")
    assert result == "Hello from Flowise"


@respx.mock
async def test_predict_returns_answer_key(client: FlowiseClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(200, json={"answer": "Answer here"})
    )
    result = await client.predict(CHATFLOW_ID, "question?")
    assert result == "Answer here"


@respx.mock
async def test_predict_returns_plain_string(client: FlowiseClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(200, json="plain string response")
    )
    result = await client.predict(CHATFLOW_ID, "hello")
    assert result == "plain string response"


@respx.mock
async def test_predict_fallback_to_str(client: FlowiseClient) -> None:
    """When response has no known text key, fall back to str(data)."""
    respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(200, json={"unknown_key": "value"})
    )
    result = await client.predict(CHATFLOW_ID, "hello")
    assert "unknown_key" in result


@respx.mock
async def test_predict_sends_session_id(client: FlowiseClient) -> None:
    route = respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(200, json={"text": "ok"})
    )
    await client.predict(CHATFLOW_ID, "hello", session_id="sess-001")
    assert route.called
    payload = route.calls[0].request
    import json
    body = json.loads(payload.content)
    assert body["sessionId"] == "sess-001"


@respx.mock
async def test_predict_raises_on_401(client: FlowiseClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(401)
    )
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.predict(CHATFLOW_ID, "hello")
    assert exc_info.value.response.status_code == 401


@respx.mock
async def test_predict_raises_on_500(client: FlowiseClient) -> None:
    respx.post(f"{BASE_URL}/api/v1/prediction/{CHATFLOW_ID}").mock(
        return_value=httpx.Response(500, json={"message": "Internal Server Error"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.predict(CHATFLOW_ID, "hello")


# ── list_chatflows ───────────────────────────────────────────────────────────

@respx.mock
async def test_list_chatflows_success(client: FlowiseClient) -> None:
    mock_data = [
        {"id": "aaa", "name": "Wiki RAG"},
        {"id": "bbb", "name": "FAQ Bot"},
    ]
    respx.get(f"{BASE_URL}/api/v1/chatflows").mock(
        return_value=httpx.Response(200, json=mock_data)
    )
    result = await client.list_chatflows()
    assert result == mock_data


@respx.mock
async def test_list_chatflows_raises_on_403(client: FlowiseClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/chatflows").mock(
        return_value=httpx.Response(403)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.list_chatflows()


# ── ping ─────────────────────────────────────────────────────────────────────

@respx.mock
async def test_ping_true_on_success(client: FlowiseClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/chatflows").mock(
        return_value=httpx.Response(200, json=[])
    )
    assert await client.ping() is True


@respx.mock
async def test_ping_false_on_error(client: FlowiseClient) -> None:
    respx.get(f"{BASE_URL}/api/v1/chatflows").mock(
        return_value=httpx.Response(500)
    )
    assert await client.ping() is False
