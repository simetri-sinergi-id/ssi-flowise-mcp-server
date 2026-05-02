## [Unreleased]

## [0.1.1] — 2026-05-02

### Fixed
- Remove README.md and CHANGELOG.md from .dockerignore — hatchling requires README.md during wheel build

### Added
- Initial release: expose Flowise chatflows as MCP tools via `streamable-http`, `sse`, or `stdio` transport
- `FLOWISE_TOOLS` for explicit chatflow → tool mapping
- `FLOWISE_AUTO_DISCOVER` to auto-register all chatflows
- Multi-stage Docker image with non-root user
- Pydantic-based settings with full validation
- Async `FlowiseClient` with httpx
