# flowise-mcp-server

[![PyPI version](https://img.shields.io/pypi/v/flowise-mcp-server.svg)](https://pypi.org/project/flowise-mcp-server/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An [MCP](https://modelcontextprotocol.io/) server that **exposes Flowise chatflows as callable tools** for AI agents (Claude.ai, Claude Desktop, VS Code Copilot, etc.).

Unlike other Flowise MCP packages that let an AI *manage* Flowise (create/delete flows), this server lets your AI *call* a Flowise RAG chatflow as a tool — i.e. it bridges your AI agent to your Flowise knowledge base.

```
Claude.ai  ──MCP──►  flowise-mcp-server  ──REST──►  Flowise  ──►  pgvector / RAG
```

## Features

- **Explicit tool mapping** — configure exactly which chatflows to expose and under what name/description
- **Auto-discovery** — optionally register all chatflows from your Flowise instance automatically
- **Multiple transports** — `streamable-http` (recommended for remote), `sse`, or `stdio`
- **Production-ready** — non-root Docker image, Pydantic v2 config validation, async httpx client
- **PyPI-publishable** — `src/` layout, `hatchling` build backend, typed

---

## Quick Start

### Option A — pip / uvx

```bash
pip install flowise-mcp-server

# or with uv (no install needed)
uvx flowise-mcp-server
```

### Option B — Docker

```bash
docker run --rm \
  -e FLOWISE_BASE_URL=https://flowise.example.com \
  -e FLOWISE_API_KEY=your-api-key \
  -e FLOWISE_TOOLS='[{"id":"<chatflow-uuid>","name":"search_wiki","description":"Search internal Wiki.js"}]' \
  -p 8000:8000 \
  ghcr.io/andhit-r/flowise-mcp-server:latest
```

---

## Configuration

All settings are read from environment variables (or a `.env` file in the working directory).

| Variable | Required | Default | Description |
|---|---|---|---|
| `FLOWISE_BASE_URL` | ✅ | — | Flowise base URL, e.g. `https://flowise.example.com` |
| `FLOWISE_API_KEY` | ✅ | — | API key from Flowise → Settings → API Keys |
| `FLOWISE_TIMEOUT` | | `60` | HTTP request timeout (seconds) |
| `FLOWISE_TOOLS` | * | — | JSON array of chatflow configs (see below) |
| `FLOWISE_AUTO_DISCOVER` | * | `false` | Auto-register all chatflows from Flowise |
| `WIKIJS_GRAPHQL_URL` | | — | Wiki.js GraphQL endpoint, e.g. `https://wiki.example.com/graphql`. When set together with `WIKIJS_API_KEY`, registers the `fetch_wiki_page` tool. |
| `WIKIJS_API_KEY` | | — | Wiki.js API key (Admin → API Access) |
| `WIKIJS_LOCALE` | | `id` | Default locale for page lookups when the path passed to `fetch_wiki_page` has no locale prefix (e.g. `id` or `en`) |
| `MCP_HOST` | | `0.0.0.0` | Host to bind |
| `MCP_PORT` | | `8000` | Port to listen on |
| `MCP_TRANSPORT` | | `streamable-http` | `streamable-http` / `sse` / `stdio` |
| `MCP_LOG_LEVEL` | | `info` | `debug` / `info` / `warning` / `error` |
| `MCP_API_KEY` | ** | — | Static Bearer API key for non-OAuth clients (must not be blank) |
| `MCP_BASE_URL` | ** | — | Public URL of this server (OAuth) |
| `AUTHENTIK_BASE_URL` | ** | — | Authentik base URL (OAuth) |
| `AUTHENTIK_APP_SLUG` | ** | — | Slug of the Authentik OAuth2/OIDC provider (OAuth) |
| `AUTHENTIK_CLIENT_ID` | ** | — | Authentik client ID (OAuth) |
| `AUTHENTIK_CLIENT_SECRET` | ** | — | Authentik client secret (OAuth) |
| `MCP_ALLOW_ANONYMOUS` | | `false` | Allow HTTP transports to start without auth (trusted networks only) |
| `MCP_STATE_DIR` | | fastmcp user-data dir (`/data` in the image) | Where OAuth client registrations are persisted |

*Either `FLOWISE_TOOLS` or `FLOWISE_AUTO_DISCOVER=true` must be set.

**Auth (`streamable-http` / `sse`):** the server refuses to start (exit 1,
`Configuration error`) unless `MCP_API_KEY` and/or the five OAuth variables
(`MCP_BASE_URL` + the four `AUTHENTIK_*`) are set, or `MCP_ALLOW_ANONYMOUS=true`.
OAuth is all-or-nothing: a partial set is a start-up error. `stdio` is exempt.
Who may log in is decided by the Authentik policy bound to the application.

### Authentication

- **Claude.ai connector (OAuth):** set the OAuth variables, then add the connector with
  only the URL (`https://<host>/mcp`) — Client ID/secret are not needed because dynamic
  client registration stays enabled (`/.well-known/oauth-authorization-server`). In
  Authentik, register `https://<MCP_BASE_URL host>/auth/callback` as the redirect URI.
- **Other clients:** send `Authorization: Bearer <MCP_API_KEY>`.
- `GET /health` → `200 {"status": "ok"}`, no credentials, no pgvector/Ollama access.
- Both can be active at once. Requests to `/mcp` without a valid token get `401`.

#### OAuth storage (persist this)

The OAuth proxy (`fastmcp` 3.2) keeps dynamically registered clients and issued-token
state in an encrypted file store under `MCP_STATE_DIR` (default: fastmcp's user-data
dir). The encryption and JWT signing keys are derived from `AUTHENTIK_CLIENT_SECRET`, so
they are stable across restarts, but the files themselves are lost when the container is
recreated — Claude.ai would then have to reconnect. The Docker image sets
`MCP_STATE_DIR=/data` (owned by the non-root user); mount a volume there:

```yaml
volumes:
  - flowise-mcp-state:/data
```

Rotating `AUTHENTIK_CLIENT_SECRET` invalidates stored state (clients re-register).

### FLOWISE_TOOLS format

```json
[
  {
    "id": "c7830e61-9629-4d56-9100-e49b0c2f17d2",
    "name": "search_wiki",
    "description": "Search the internal Wiki.js knowledge base for company policies, procedures, and technical guides."
  }
]
```

- `id` — the chatflow UUID from Flowise
- `name` — valid Python identifier used as the MCP tool name
- `description` — shown to the AI agent; be descriptive so the agent knows when to call it

---

## MCP Client Configuration

### Claude.ai (Remote MCP Connector)

Add a new connector in Claude.ai Settings → Integrations → Remote MCP:

```
URL: https://your-mcp-server.example.com/mcp
```

> The server must be accessible via HTTPS. Use Traefik or another reverse proxy for TLS termination.

### Claude Desktop

```json
{
  "mcpServers": {
    "flowise": {
      "command": "uvx",
      "args": ["flowise-mcp-server"],
      "env": {
        "FLOWISE_BASE_URL": "https://flowise.example.com",
        "FLOWISE_API_KEY": "your-api-key",
        "FLOWISE_TOOLS": "[{\"id\":\"<uuid>\",\"name\":\"search_wiki\",\"description\":\"...\"}]",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

### VS Code (GitHub Copilot)

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "flowise": {
      "command": "uvx",
      "args": ["flowise-mcp-server"],
      "env": {
        "FLOWISE_BASE_URL": "https://flowise.example.com",
        "FLOWISE_API_KEY": "your-api-key",
        "FLOWISE_TOOLS": "[{\"id\":\"<uuid>\",\"name\":\"search_wiki\",\"description\":\"...\"}]",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

---

## Docker Deployment with Traefik

For production deployment behind Traefik (exposes `/mcp` endpoint over HTTPS):

```yaml
# In your docker-compose.yml
services:
  flowise-mcp:
    image: ghcr.io/andhit-r/flowise-mcp-server:latest
    env_file: .env
    networks:
      - inverseproxy_shared
      - default
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=inverseproxy_shared"
      - "traefik.http.routers.flowise-mcp.rule=Host(`${MCP_DOMAIN}`) && PathPrefix(`/mcp`)"
      - "traefik.http.routers.flowise-mcp.entrypoints=https"
      - "traefik.http.routers.flowise-mcp.tls.certresolver=letsencrypt"
      - "traefik.http.services.flowise-mcp.loadbalancer.server.port=8000"
```

Claude.ai MCP URL: `https://your-mcp-domain.example.com/mcp`

---

## Development

```bash
git clone https://github.com/andhit-r/flowise-mcp-server.git
cd flowise-mcp-server

# Create virtual environment and install with dev extras
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov

# Lint & format
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/
```

### Project Structure

```
flowise-mcp-server/
├── src/
│   └── flowise_mcp_server/
│       ├── __init__.py     # package version
│       ├── __main__.py     # python -m support
│       ├── cli.py          # entry point
│       ├── settings.py     # pydantic-settings config
│       ├── auth_provider.py # Authentik OAuth + API-key verifier
│       ├── asgi.py         # Starlette app: MCP + /health
│       ├── client.py       # async Flowise HTTP client
│       └── server.py       # FastMCP server factory
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_client.py
│   └── test_server.py
├── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Building & Publishing to PyPI

```bash
pip install hatchling build twine

# Build wheel + sdist
python -m build

# Upload to PyPI
twine upload dist/*
```

### Building the Docker Image

```bash
docker build -t flowise-mcp-server:latest .

# Multi-platform (for CI/CD)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/andhit-r/flowise-mcp-server:latest \
  --push .
```

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Andhitia Rama &lt;andhitia.r@gmail.com&gt;
