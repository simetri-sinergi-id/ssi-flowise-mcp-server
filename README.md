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
| `MCP_HOST` | | `0.0.0.0` | Host to bind |
| `MCP_PORT` | | `8000` | Port to listen on |
| `MCP_TRANSPORT` | | `streamable-http` | `streamable-http` / `sse` / `stdio` |
| `MCP_LOG_LEVEL` | | `info` | `debug` / `info` / `warning` / `error` |

*Either `FLOWISE_TOOLS` or `FLOWISE_AUTO_DISCOVER=true` must be set.

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
│       ├── client.py       # async Flowise HTTP client
│       └── server.py       # FastMCP server factory
├── tests/
│   ├── conftest.py
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
