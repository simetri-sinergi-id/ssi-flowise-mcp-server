# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tool (hatchling)
RUN pip install --no-cache-dir hatchling

# Copy project metadata first to leverage Docker layer cache for dependencies.
# A stub __init__.py lets pip resolve extras without the full source.
COPY pyproject.toml README.md ./
RUN mkdir -p src/flowise_mcp_server \
    && touch src/flowise_mcp_server/__init__.py \
    && pip install --no-cache-dir ".[dev]" 2>/dev/null \
    || pip install --no-cache-dir .

# Now copy the real source and do a no-deps install so the wheel is built
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps --no-build-isolation .

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="flowise-mcp-server" \
      org.opencontainers.image.description="MCP server that exposes Flowise chatflows as tools" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/andhit-r/flowise-mcp-server"

WORKDIR /app

# Copy installed packages and the entry-point script from the builder
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/flowise-mcp-server \
                    /usr/local/bin/flowise-mcp-server

# Non-root user for least-privilege principle
RUN useradd --create-home --uid 1000 --shell /bin/bash app
USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["flowise-mcp-server"]
