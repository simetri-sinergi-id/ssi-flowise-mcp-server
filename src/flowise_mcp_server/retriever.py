"""Direct pgvector retrieval: embed query via Ollama, search via pgvector."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
import psycopg2
import psycopg2.extras

if TYPE_CHECKING:
    from .settings import Settings

logger = logging.getLogger(__name__)


async def _embed(ollama_base_url: str, model: str, text: str, timeout: int) -> list[float]:
    """Call Ollama embeddings API and return the embedding vector."""
    url = f"{ollama_base_url.rstrip('/')}/api/embeddings"
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json={"model": model, "prompt": text})
        response.raise_for_status()
    return response.json()["embedding"]


def _pg_search(
    *,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
    table: str,
    embedding: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    """Synchronous pgvector similarity search (cosine distance via <=>)."""
    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
    conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT
                    "pageContent" AS content,
                    "metadata"
                FROM "{table}"
                ORDER BY "embedding" <=> %s::vector
                LIMIT %s
                """,
                (vector_str, top_k),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


async def retrieve(settings: Settings, query: str) -> str:
    """Embed *query*, search pgvector, return formatted context for the AI agent.

    Args:
        settings: Application settings with pgvector + Ollama config populated.
        query: The natural-language search query.

    Returns:
        Formatted string of top-k document chunks suitable as LLM context.
    """
    assert settings.ollama_base_url, "ollama_base_url must be set for direct retrieval"
    assert settings.pgvector_host, "pgvector_host must be set for direct retrieval"

    logger.debug("Embedding query via Ollama: %r", query[:80])
    embedding = await _embed(
        settings.ollama_base_url,
        settings.embedding_model,
        query,
        settings.flowise_timeout,
    )

    import asyncio

    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(
        None,
        lambda: _pg_search(
            host=settings.pgvector_host,  # type: ignore[arg-type]
            port=settings.pgvector_port,
            dbname=settings.pgvector_db,  # type: ignore[arg-type]
            user=settings.pgvector_user,  # type: ignore[arg-type]
            password=settings.pgvector_pass,  # type: ignore[arg-type]
            table=settings.pgvector_table,
            embedding=embedding,
            top_k=settings.top_k,
        ),
    )

    if not rows:
        return "No relevant documents found."

    parts: list[str] = []
    for i, row in enumerate(rows, 1):
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        title = meta.get("title", "Untitled")
        source = meta.get("source", "")
        content = (row.get("content") or "").strip()
        parts.append(f"[{i}] **{title}**{f' ({source})' if source else ''}\n{content}")

    return "\n\n---\n\n".join(parts)
