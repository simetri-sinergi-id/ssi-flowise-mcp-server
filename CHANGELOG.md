## [Unreleased]

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
