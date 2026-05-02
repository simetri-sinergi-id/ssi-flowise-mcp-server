"""Async HTTP client for the Flowise REST API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Response keys returned by Flowise depending on the flow/version
_TEXT_KEYS = ("text", "answer", "output", "result")


class FlowiseClient:
    """Thin async wrapper around the Flowise prediction and management APIs."""

    def __init__(self, base_url: str, api_key: str, timeout: int = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    # ── Prediction ──────────────────────────────────────────────────────────

    async def predict(
        self,
        chatflow_id: str,
        question: str,
        session_id: str | None = None,
        override_config: dict[str, Any] | None = None,
    ) -> str:
        """Send *question* to a Flowise chatflow and return the text response.

        Args:
            chatflow_id: UUID of the Flowise chatflow.
            question: The user question or query string.
            session_id: Optional session ID for multi-turn conversations.
            override_config: Optional dict of node-level overrides (``overrideConfig``).

        Returns:
            The text answer from Flowise.

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx HTTP responses.
            httpx.TimeoutException: If the request exceeds *timeout* seconds.
        """
        payload: dict[str, Any] = {"question": question}
        if session_id:
            payload["sessionId"] = session_id
        if override_config:
            payload["overrideConfig"] = override_config

        url = f"{self._base_url}/api/v1/prediction/{chatflow_id}"
        logger.debug("POST %s  question=%r", url, question[:120])

        async with httpx.AsyncClient(timeout=self._timeout) as http:
            response = await http.post(url, headers=self._headers, json=payload)
            response.raise_for_status()

        data: Any = response.json()

        # Flowise may return a plain string or a dict with various key names
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            for key in _TEXT_KEYS:
                if key in data and isinstance(data[key], str):
                    return data[key]
        return str(data)

    # ── Management ──────────────────────────────────────────────────────────

    async def list_chatflows(self) -> list[dict[str, Any]]:
        """Return all chatflows visible with the current API key.

        Raises:
            httpx.HTTPStatusError: On 4xx/5xx responses.
        """
        url = f"{self._base_url}/api/v1/chatflows"
        logger.debug("GET %s", url)

        async with httpx.AsyncClient(timeout=self._timeout) as http:
            response = await http.get(url, headers=self._headers)
            response.raise_for_status()

        result: list[dict[str, Any]] = response.json()
        return result

    async def ping(self) -> bool:
        """Return True if the Flowise instance is reachable and the API key is valid."""
        try:
            await self.list_chatflows()
            return True
        except (httpx.HTTPError, Exception):
            return False
