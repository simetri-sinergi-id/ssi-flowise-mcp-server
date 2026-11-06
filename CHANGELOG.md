## [Unreleased]

## [0.4.0] - 2026-11-06

### Added
- Front-door auth for the HTTP transports: Authentik OAuth (`AuthentikProvider`, dynamic
  client registration stays on so the Claude.ai connector only needs the URL) and Bearer
  API key (`BearerApiKeyVerifier`, constant-time compare), combined with `MultiAuth` when
  both are active. New env: `MCP_BASE_URL`, `AUTHENTIK_BASE_URL`, `AUTHENTIK_APP_SLUG`,
  `AUTHENTIK_CLIENT_ID`, `AUTHENTIK_CLIENT_SECRET`, `MCP_API_KEY`, `MCP_ALLOW_ANONYMOUS`,
  `MCP_STATE_DIR`.
- `GET /health` (200 `{"status": "ok"}`, no auth) for container health checks.
- Docker image: `/data` volume holding OAuth client registrations (`MCP_STATE_DIR=/data`).

### Changed
- **BREAKING:** `streamable-http` / `sse` now refuse to start (`Configuration error`,
  exit 1) without auth. Set `MCP_API_KEY` and/or the OAuth variables, or
  `MCP_ALLOW_ANONYMOUS=true`. **Deployments without auth that track the `latest` tag MUST
  set `MCP_ALLOW_ANONYMOUS=true` before pulling the new image**, or the container will
  fail to start. `stdio` is unaffected. Partial OAuth config and a blank `MCP_API_KEY`
  are also start-up errors.
- HTTP transports are now served by uvicorn from a Starlette app (MCP path stays `/mcp`).
- `fastmcp` is pinned to `>=3.2,<3.3` (was `>=2.0.0`); `uvicorn>=0.30` added.

### Fixed
- Two `build_server` tests used the private `_tool_manager` API removed in fastmcp 3.x;
  they now use `await mcp.list_tools()`. Pre-existing lint errors fixed.

## [0.3.1] — 2026-07-13

### Fixed
- `fetch_wiki_page` always failed (`Page not found`) when given a path with a locale
  prefix (e.g. `/en/master-data/lokasi`, as shown in search results and browser URLs) —
  the locale segment was left in the path instead of being passed as the separate
  `locale` GraphQL argument, so the query never matched any page.
- Added `_normalise()` helper in `wikijs.py` to split a locale prefix (or a full URL)
  out of the path, plus a one-shot retry with the original path when the stripped
  segment turns out to be a real top-level page name rather than a locale code.
- Error and not-found messages from `fetch_wiki_page` now include the path and locale
  actually used, to make misconfiguration easier to diagnose.
- Documented `WIKIJS_LOCALE` in `README.md`'s configuration table (was only in
  `.env.example`).

## [0.3.0] — 2026-05-08

### Added
- `fetch_wiki_page` MCP tool: fetch full markdown content of any Wiki.js page by path
- New `wikijs.py` module with async GraphQL client for Wiki.js `pages.singleByPath`
- Three new env vars: `WIKIJS_GRAPHQL_URL`, `WIKIJS_API_KEY`, `WIKIJS_LOCALE` (default: `id`)
- Tool is registered automatically when both `WIKIJS_GRAPHQL_URL` and `WIKIJS_API_KEY` are set
- Server instructions updated to guide AI agents to use `fetch_wiki_page` when following links from search results

## [0.2.0] — 2026-05-02

### Added
- Direct pgvector + Ollama retrieval mode (`PGVECTOR_HOST`, `PGVECTOR_DB`, `PGVECTOR_USER`, `PGVECTOR_PASS`, `OLLAMA_BASE_URL`)
- When direct mode is active, tools bypass Flowise prediction API and query pgvector directly
- New `retriever.py` module: embed via Ollama `/api/embeddings`, search via cosine similarity (`<=>` operator)
- `TOP_K` env var to control number of returned chunks (default: 5)
- `psycopg2-binary` added as core dependency

### Fixed
- Flowise prediction API 500 error when chatflow has no LLM node

### Fixed
- Remove README.md and CHANGELOG.md from .dockerignore — hatchling requires README.md during wheel build

### Added
- Initial release: expose Flowise chatflows as MCP tools via `streamable-http`, `sse`, or `stdio` transport
- `FLOWISE_TOOLS` for explicit chatflow → tool mapping
- `FLOWISE_AUTO_DISCOVER` to auto-register all chatflows
- Multi-stage Docker image with non-root user
- Pydantic-based settings with full validation
- Async `FlowiseClient` with httpx
