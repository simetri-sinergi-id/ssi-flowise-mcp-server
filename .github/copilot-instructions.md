# Copilot Instructions — ssi-flowise-mcp-server

## Versioning & Tagging

### Scheme
`v<MAJOR>.<MINOR>.<PATCH>` — semantic versioning.

| Segment | When to increment |
|---|---|
| `MAJOR` | Breaking change: renamed tools, removed env vars, changed transport defaults |
| `MINOR` | New feature: new tool, new env var, auto-discover support, new transport |
| `PATCH` | Bug fix, refactor, lint/style, docs, dependency update |

### When to create a tag
Create a new git tag **only when** at least one of these is true:
- A bug is fixed that affected production behaviour
- A new feature was added
- A breaking change was made

**Do NOT tag** for:
- Docs-only changes (README, comments)
- `.env.example` updates with no code change
- Copilot instruction / dev tooling changes (pre-commit, ruff config)

### Workflow
```bash
# After commit:
git tag v0.X.Y
git push origin master
git push origin v0.X.Y
```

Always push both `master` and the tag separately.
Never use `--force` on tags that have already been pushed.

### Version file
The canonical version lives in **`src/flowise_mcp_server/__init__.py`**:
```python
__version__ = "0.1.0"
```
Also update `pyproject.toml` `[project] version` to match before tagging.

### Current version history
| Tag | Description |
|---|---|
| v0.1.0 | Initial release: expose Flowise chatflows as MCP tools |
| v0.1.1 | Fix .dockerignore excluded README.md (Docker build failure) |

---

## Project Overview

**ssi-flowise-mcp-server** — MCP server that exposes Flowise chatflows as callable tools
for AI agents (Claude.ai, Claude Desktop, VS Code Copilot, etc.).

- Transport: `stdio` (local) or `streamable-http` / `sse` (remote)
- Auth: Flowise API key passed as `Authorization: Bearer` header
- Use case: RAG chatflows exposed as MCP tools (e.g. `search_wiki`)

## Key Files

| File | Purpose |
|---|---|
| `src/flowise_mcp_server/settings.py` | Pydantic-settings config, ToolConfig dataclass |
| `src/flowise_mcp_server/client.py` | Async httpx client for Flowise prediction + management APIs |
| `src/flowise_mcp_server/server.py` | FastMCP factory: register chatflows as tools |
| `src/flowise_mcp_server/cli.py` | CLI entry point, logging setup |

## Tool Configuration

```dotenv
# Explicit (recommended — give precise descriptions for the AI agent)
FLOWISE_TOOLS=[{"id":"<uuid>","name":"search_wiki","description":"Search internal Wiki.js"}]

# Auto-discover all chatflows
FLOWISE_AUTO_DISCOVER=true
```

Tool `name` must be a valid Python identifier (`[a-zA-Z_][a-zA-Z0-9_]*`).

## Flowise Prediction API

```
POST /api/v1/prediction/<chatflow-id>
Authorization: Bearer <api-key>
{"question": "...", "sessionId": "..."}
```

Response: `{"text": "..."}` or `{"answer": "..."}` or plain string.

## Lint & Format

```bash
ruff check . && ruff format .
```

Pre-commit hooks run automatically on commit.

## Docker

Image: `ghcr.io/simetri-sinergi-id/ssi-flowise-mcp-server:latest`
Built by `.github/workflows/docker.yml` on push to `master` or tag `v*.*.*`.
