"""Wiki.js GraphQL client for fetching full page content by path."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit

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

_LOCALE_RE = re.compile(r"^[a-z]{2}(-[A-Za-z]{2,4})?$")


def _normalise(path: str, default_locale: str) -> tuple[str, str]:
    """Split a raw path/URL into a Wiki.js-clean path and its locale.

    Args:
        path: Absolute path (``/en/a/b``), bare path (``a/b``), or full URL
              (``https://wiki.x/en/a/b?x=1``) as it appears in search results
              or a browser address bar.
        default_locale: Locale to use when no locale prefix is present in path.

    Returns:
        Tuple of (clean_path, locale) suitable as GraphQL variables for
        ``pages.singleByPath``, which expects the locale as a separate
        argument rather than a path segment.
    """
    if path.startswith("http://") or path.startswith("https://"):
        path = urlsplit(path).path

    cleaned = unquote(path.strip("/"))
    segments = cleaned.split("/", 1)

    if segments and _LOCALE_RE.match(segments[0]):
        locale = segments[0]
        rest = segments[1] if len(segments) > 1 else ""
        return rest, locale

    return cleaned, default_locale


async def _query_page(
    client: httpx.AsyncClient, url: str, headers: dict[str, str], path: str, locale: str
) -> dict[str, Any]:
    """Run the singleByPath GraphQL query and return the decoded JSON response."""
    payload = {
        "query": _QUERY,
        "variables": {"path": path, "locale": locale},
    }
    response = await client.post(url, headers=headers, json=payload)
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


async def fetch_page(settings: Settings, path: str) -> str:
    """Fetch a Wiki.js page by its path and return formatted markdown content.

    Accepts a bare path, a path with a locale prefix (e.g. ``/en/a/b`` — as
    returned by search results and shown in the browser address bar), or a
    full URL; the locale prefix and locale argument are handled automatically.

    Args:
        settings: Application settings with wikijs_graphql_url and wikijs_api_key set.
        path: Absolute path of the page, e.g. ``/master-data/lokasi/01-membuat``.
              Leading slash, locale prefix, and full URLs are all normalised.

    Returns:
        Formatted string with page title, path, and full markdown content.
        Returns an error message string if the page is not found.
    """
    assert settings.wikijs_graphql_url, "wikijs_graphql_url must be set"
    assert settings.wikijs_api_key, "wikijs_api_key must be set"

    default_locale = settings.wikijs_locale
    normalised_path, locale = _normalise(path, default_locale)
    prefix_was_stripped = normalised_path != path.strip("/") and locale != default_locale

    headers = {
        "Authorization": f"Bearer {settings.wikijs_api_key}",
        "Content-Type": "application/json",
    }

    logger.debug("Fetching Wiki.js page: %r (locale=%s)", normalised_path, locale)

    async with httpx.AsyncClient(timeout=settings.flowise_timeout) as client:
        data = await _query_page(
            client, settings.wikijs_graphql_url, headers, normalised_path, locale
        )

        page = (data.get("data") or {}).get("pages", {}).get("singleByPath")
        errors = data.get("errors")

        # Fall back to the original (un-stripped) path + default locale in case
        # the stripped segment was actually part of the real path, not a locale
        # prefix (e.g. a top-level page that happens to be named two letters).
        if not page and not errors and prefix_was_stripped:
            retry_path = path.strip("/")
            logger.debug(
                "Page not found for %r/%s, retrying with %r/%s",
                normalised_path, locale, retry_path, default_locale,
            )
            data = await _query_page(
                client, settings.wikijs_graphql_url, headers, retry_path, default_locale
            )
            page = (data.get("data") or {}).get("pages", {}).get("singleByPath")
            errors = data.get("errors")
            normalised_path, locale = retry_path, default_locale

    if errors:
        messages = "; ".join(e.get("message", str(e)) for e in errors)
        logger.warning(
            "Wiki.js GraphQL errors for path %r (locale=%s): %s", normalised_path, locale, messages
        )
        return f"Error fetching page /{normalised_path} (locale={locale}): {messages}"

    if not page:
        return f"Page not found: /{normalised_path} (locale={locale})"

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
