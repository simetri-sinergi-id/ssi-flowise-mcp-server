"""Application settings loaded from environment variables."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, field_validator, model_validator
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

    # ── Direct pgvector retrieval mode (optional — bypasses Flowise prediction API) ──
    # When all pgvector_* and ollama_base_url are set, FLOWISE_TOOLS items
    # with matching names will use direct retrieval instead of calling Flowise.
    pgvector_host: str | None = Field(default=None, description="pgvector hostname")
    pgvector_port: int = Field(default=5432, description="pgvector port")
    pgvector_db: str | None = Field(default=None, description="pgvector database name")
    pgvector_user: str | None = Field(default=None, description="pgvector username")
    pgvector_pass: str | None = Field(default=None, description="pgvector password")
    pgvector_table: str = Field(default="wiki_docs", description="vector table name")
    ollama_base_url: str | None = Field(
        default=None,
        description="Ollama base URL for embeddings, e.g. http://ollama:11434",
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Ollama embedding model name",
    )
    top_k: int = Field(default=5, gt=0, description="Number of chunks to return per query")

    # ── Wiki.js GraphQL (optional — enables fetch_wiki_page tool) ───────────
    wikijs_graphql_url: str | None = Field(
        default=None,
        description="Wiki.js GraphQL endpoint, e.g. https://wiki.example.com/graphql",
    )
    wikijs_api_key: str | None = Field(
        default=None,
        description="Wiki.js API key (Admin → API Access)",
    )
    wikijs_locale: str = Field(
        default="id",
        description=(
            "Default locale for page lookups (e.g. 'id' or 'en'), used when the path "
            "passed to fetch_wiki_page has no locale prefix (see wikijs.py:_normalise) "
            "or as the fallback locale on retry."
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

    # ── Front-door auth (HTTP transports only) ──────────────────────────────
    mcp_base_url: str | None = Field(
        default=None,
        description="Public URL of this server (OAuth redirects), e.g. https://mcp.example.com",
    )
    authentik_base_url: str | None = Field(default=None, description="Authentik base URL")
    authentik_app_slug: str | None = Field(
        default=None, description="Slug of the Authentik OAuth2/OIDC provider application"
    )
    authentik_client_id: str | None = Field(default=None, description="Authentik client ID")
    authentik_client_secret: str | None = Field(
        default=None, description="Authentik client secret"
    )
    mcp_api_key: str | None = Field(
        default=None,
        description="Static Bearer API key for non-OAuth clients (enables API-key auth)",
    )
    mcp_allow_anonymous: bool = Field(
        default=False,
        description="Allow HTTP transports to start with no auth (NOT recommended)",
    )
    mcp_state_dir: str | None = Field(
        default=None,
        description=(
            "Directory where the OAuth proxy persists client registrations (mount a "
            "volume here so they survive container restarts)"
        ),
    )

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("mcp_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Reject an empty or whitespace-only API key."""
        if v is not None and not v.strip():
            raise ValueError("MCP_API_KEY must not be empty or whitespace")
        return v

    @model_validator(mode="after")
    def validate_oauth_complete(self) -> Settings:
        """Reject partially configured OAuth instead of silently dropping it."""
        values = self.oauth_values()
        filled = [k for k, v in values.items() if v and v.strip()]
        if filled and len(filled) != len(values):
            missing = sorted(k.upper() for k in values if k not in filled)
            raise ValueError(
                "OAuth configuration is incomplete; also set: " + ", ".join(missing)
            )
        return self

    @field_validator("flowise_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("ollama_base_url")
    @classmethod
    def strip_ollama_trailing_slash(cls, v: str | None) -> str | None:
        return v.rstrip("/") if v else v

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

    def oauth_values(self) -> dict[str, str | None]:
        """Return the five env values that together enable Authentik OAuth."""
        return {
            "mcp_base_url": self.mcp_base_url,
            "authentik_base_url": self.authentik_base_url,
            "authentik_app_slug": self.authentik_app_slug,
            "authentik_client_id": self.authentik_client_id,
            "authentik_client_secret": self.authentik_client_secret,
        }

    def is_oauth_enabled(self) -> bool:
        """Return True when all five OAuth env values are set."""
        return all(v and v.strip() for v in self.oauth_values().values())

    def is_api_key_enabled(self) -> bool:
        """Return True when ``MCP_API_KEY`` is set."""
        return bool(self.mcp_api_key)

    def is_auth_enabled(self) -> bool:
        """Return True when at least one front-door auth mechanism is active."""
        return self.is_oauth_enabled() or self.is_api_key_enabled()

    def check_auth_policy(self) -> None:
        """Fail closed: HTTP transports must have auth unless anonymous is allowed.

        Raises:
            ValueError: transport is ``streamable-http``/``sse``, no auth is
                configured and ``MCP_ALLOW_ANONYMOUS`` is not true.
        """
        if self.mcp_transport == "stdio" or self.is_auth_enabled():
            return
        if self.mcp_allow_anonymous:
            logger.warning("HTTP transport running WITHOUT auth (MCP_ALLOW_ANONYMOUS=true)")
            return
        raise ValueError(
            f"transport {self.mcp_transport!r} requires auth: set MCP_API_KEY and/or the "
            "OAuth variables (MCP_BASE_URL + AUTHENTIK_*), or MCP_ALLOW_ANONYMOUS=true"
        )

    def is_direct_mode(self) -> bool:
        """Return True when direct pgvector + Ollama retrieval is configured."""
        return all([
            self.pgvector_host,
            self.pgvector_db,
            self.pgvector_user,
            self.pgvector_pass,
            self.ollama_base_url,
        ])

    def is_wikijs_configured(self) -> bool:
        """Return True when Wiki.js GraphQL fetch tool can be registered."""
        return bool(self.wikijs_graphql_url and self.wikijs_api_key)

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
