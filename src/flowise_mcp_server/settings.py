"""Application settings loaded from environment variables."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


@dataclass
class ToolConfig:
    """Configuration for a single Flowise chatflow to expose as an MCP tool."""

    id: str
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.description:
            self.description = f"Query Flowise chatflow {self.id[:8]}"
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.name):
            raise ValueError(
                f"Tool name {self.name!r} must be a valid identifier "
                "(letters, digits, underscores; must not start with a digit)."
            )


class Settings(BaseSettings):
    """All configuration via environment variables (or .env file)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Flowise connection ──────────────────────────────────────────────────
    flowise_base_url: Annotated[
        str,
        Field(description="Base URL of the Flowise instance, e.g. https://flowise.example.com"),
    ]
    flowise_api_key: Annotated[
        str,
        Field(description="Flowise API key (Settings → API Keys)"),
    ]
    flowise_timeout: int = Field(
        default=60,
        gt=0,
        description="HTTP request timeout in seconds",
    )

    # ── Tool configuration ──────────────────────────────────────────────────
    flowise_tools: str | None = Field(
        default=None,
        description=(
            "JSON array of chatflow tool configs. "
            'Example: [{"id": "<uuid>", "name": "search_wiki", "description": "..."}]'
        ),
    )
    flowise_auto_discover: bool = Field(
        default=False,
        description=(
            "When true and FLOWISE_TOOLS is not set, auto-discover ALL chatflows "
            "from the Flowise instance and register each as an MCP tool."
        ),
    )

    # ── MCP server ──────────────────────────────────────────────────────────
    mcp_host: str = Field(default="0.0.0.0", description="Host to bind")
    mcp_port: int = Field(default=8000, gt=0, lt=65536, description="Port to listen on")
    mcp_transport: str = Field(
        default="streamable-http",
        description="MCP transport: 'streamable-http' (recommended), 'sse', or 'stdio'",
    )
    mcp_log_level: str = Field(
        default="info",
        description="Log level: debug | info | warning | error",
    )

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("flowise_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("mcp_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"debug", "info", "warning", "error", "critical"}
        lower = v.lower()
        if lower not in valid:
            raise ValueError(f"mcp_log_level must be one of {sorted(valid)}, got {v!r}")
        return lower

    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        valid = {"streamable-http", "sse", "stdio"}
        if v not in valid:
            raise ValueError(f"mcp_transport must be one of {sorted(valid)}, got {v!r}")
        return v

    # ── Helpers ─────────────────────────────────────────────────────────────

    def get_tools(self) -> list[ToolConfig]:
        """Parse FLOWISE_TOOLS JSON and return validated tool configs."""
        if not self.flowise_tools:
            return []
        try:
            raw: list[dict[str, str]] = json.loads(self.flowise_tools)
        except json.JSONDecodeError as exc:
            raise ValueError(f"FLOWISE_TOOLS is not valid JSON: {exc}") from exc
        if not isinstance(raw, list):
            raise ValueError("FLOWISE_TOOLS must be a JSON array")
        tools: list[ToolConfig] = []
        for item in raw:
            if "id" not in item or "name" not in item:
                raise ValueError(f"Each tool config must have 'id' and 'name' keys, got: {item}")
            tools.append(
                ToolConfig(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description", ""),
                )
            )
        return tools
