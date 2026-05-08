"""Wiki.js GraphQL client for fetching full page content by path."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .settings import Settings

logger = logging.getLogger(__name__)

_QUERY = """
query FetchPage($path: String!, $locale: String!) {
  pages {
    singleByPath(path: $path, locale: $locale) {
      id
      title
      description
      path
      content
      updatedAt
    }
  }
}
"""


async def fetch_page(settings: Settings, path: str) -> str:
    """Fetch a Wiki.js page by its path and return formatted markdown content.

    Args:
        settings: Application settings with wikijs_graphql_url and wikijs_api_key set.
        path: Absolute path of the page, e.g. ``/master-data/lokasi/01-membuat``.
              Leading slash is optional and will be normalised.

    Returns:
        Formatted string with page title, path, and full markdown content.
        Returns an error message string if the page is not found.
    """
    assert settings.wikijs_graphql_url, "wikijs_graphql_url must be set"
    assert settings.wikijs_api_key, "wikijs_api_key must be set"

    # Normalise path — Wiki.js expects no leading slash in singleByPath
    normalised_path = path.lstrip("/")

    headers = {
        "Authorization": f"Bearer {settings.wikijs_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": _QUERY,
        "variables": {
            "path": normalised_path,
            "locale": settings.wikijs_locale,
        },
    }

    logger.debug("Fetching Wiki.js page: %r (locale=%s)", normalised_path, settings.wikijs_locale)

    async with httpx.AsyncClient(timeout=settings.flowise_timeout) as client:
        response = await client.post(
            settings.wikijs_graphql_url,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    data = response.json()

    errors = data.get("errors")
    if errors:
        messages = "; ".join(e.get("message", str(e)) for e in errors)
        logger.warning("Wiki.js GraphQL errors for path %r: %s", normalised_path, messages)
        return f"Error fetching page /{normalised_path}: {messages}"

    page = (data.get("data") or {}).get("pages", {}).get("singleByPath")
    if not page:
        return f"Page not found: /{normalised_path}"

    title = page.get("title") or "(no title)"
    description = page.get("description") or ""
    full_path = page.get("path") or normalised_path
    updated_at = page.get("updatedAt") or ""
    content = (page.get("content") or "").strip()

    header_lines = [f"# {title}", f"Path: /{full_path}"]
    if description:
        header_lines.append(f"Description: {description}")
    if updated_at:
        header_lines.append(f"Last updated: {updated_at}")

    return "\n".join(header_lines) + "\n\n---\n\n" + content
