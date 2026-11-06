"""Front-door auth for the HTTP transports: Authentik OAuth and a static API key.

``AuthentikProvider`` lets Claude.ai log in through Authentik (OAuth 2.0 authorization
code + PKCE, dynamic client registration stays on). ``BearerApiKeyVerifier`` serves
non-OAuth clients with a static Bearer token. Who may log in is decided by the Authentik
policy, not by this server. Pattern follows ``andhit-r/flowise-mcp``.
"""

from __future__ import annotations

import hmac
import logging
from typing import TYPE_CHECKING, Any

import httpx
from fastmcp.server.auth import AccessToken, MultiAuth, TokenVerifier
from fastmcp.server.auth.oauth_proxy.proxy import OAuthProxy
from fastmcp.server.auth.providers.jwt import JWTVerifier
from mcp.server.auth.provider import TokenError

if TYPE_CHECKING:
    from fastmcp.server.auth import AuthProvider

    from .settings import Settings

logger = logging.getLogger(__name__)


class AuthentikProvider(OAuthProxy):
    """OAuthProxy that uses Authentik as the identity provider.

    Args:
        authentik_base_url: Authentik base URL.
        application_slug: Slug of the OAuth2/OIDC provider in Authentik.
        client_id: Authentik OAuth2 client ID.
        client_secret: Authentik OAuth2 client secret.
        base_url: Public URL of this MCP server.
        **kwargs: Forwarded to ``OAuthProxy.__init__``.
    """

    def __init__(
        self,
        *,
        authentik_base_url: str,
        application_slug: str,
        client_id: str,
        client_secret: str,
        base_url: str,
        **kwargs: Any,
    ) -> None:
        base = authentik_base_url.rstrip("/")
        slug = application_slug.strip("/")
        issuer_url = f"{base}/application/o/{slug}/"
        self._userinfo_url = f"{base}/application/o/userinfo/"

        super().__init__(
            upstream_authorization_endpoint=f"{base}/application/o/authorize/",
            upstream_token_endpoint=f"{base}/application/o/token/",
            upstream_client_id=client_id,
            upstream_client_secret=client_secret,
            upstream_revocation_endpoint=f"{base}/application/o/{slug}/end-session/",
            token_verifier=JWTVerifier(
                jwks_uri=f"{base}/application/o/{slug}/jwks/", issuer=issuer_url
            ),
            base_url=base_url,
            valid_scopes=["openid", "profile", "email"],
            **kwargs,
        )
        logger.debug("AuthentikProvider ready, issuer: %s", issuer_url)

    async def _extract_upstream_claims(self, idp_tokens: dict[str, Any]) -> dict[str, Any] | None:
        """Fetch user claims from Authentik userinfo during the code exchange.

        Raises:
            TokenError: upstream token missing, userinfo unreachable or rejected, or no
                username. ``error_code`` MUST be one of ``invalid_request``,
                ``invalid_client``, ``invalid_grant``, ``unauthorized_client``,
                ``unsupported_grant_type``, ``invalid_scope``; any other code makes the
                token endpoint crash with a Pydantic ValidationError.
        """
        access_token = idp_tokens.get("access_token", "")
        if not access_token:
            raise TokenError("invalid_grant", "Upstream access token is not available")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self._userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.RequestError as exc:
            logger.warning("Could not reach Authentik userinfo: %s", exc)
            raise TokenError(
                "invalid_request", "Could not verify identity with Authentik"
            ) from exc

        if response.status_code != 200:
            logger.warning("Authentik userinfo rejected token (status=%d)", response.status_code)
            raise TokenError("invalid_grant", "Authentik token is invalid or expired")

        userinfo = response.json()
        username: str = (
            (userinfo.get("preferred_username") or userinfo.get("sub", "")).lower().strip()
        )
        if not username:
            raise TokenError("invalid_grant", "Could not read username from Authentik")

        logger.info("Authentik user '%s' authenticated", username)
        return {
            "username": username,
            "email": userinfo.get("email"),
            "name": userinfo.get("name"),
            "sub": userinfo.get("sub"),
            "groups": userinfo.get("groups", []),
        }


class BearerApiKeyVerifier(TokenVerifier):
    """Verify a static Bearer token (API key) in constant time.

    Args:
        api_key: The expected key.

    Raises:
        ValueError: ``api_key`` is empty or whitespace.
    """

    def __init__(self, *, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("api_key must not be empty")
        self._api_key = api_key

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an ``AccessToken`` when *token* equals the API key, else ``None``."""
        if hmac.compare_digest(token.encode(), self._api_key.encode()):
            return AccessToken(token=token, client_id="api-key-client", scopes=[])
        return None


def build_auth(settings: Settings) -> AuthProvider | None:
    """Build the front-door auth provider from settings.

    Args:
        settings: Validated settings.

    Returns:
        ``AuthentikProvider`` (OAuth), a ``MultiAuth`` of the API-key verifier alone or
        combined with OAuth, or ``None`` when no auth is configured.
    """
    verifiers: list[TokenVerifier] = []
    if settings.mcp_api_key:
        verifiers.append(BearerApiKeyVerifier(api_key=settings.mcp_api_key))

    provider: AuthentikProvider | None = None
    if settings.is_oauth_enabled():
        assert settings.authentik_base_url and settings.authentik_app_slug
        assert settings.authentik_client_id and settings.authentik_client_secret
        assert settings.mcp_base_url
        provider = AuthentikProvider(
            authentik_base_url=settings.authentik_base_url,
            application_slug=settings.authentik_app_slug,
            client_id=settings.authentik_client_id,
            client_secret=settings.authentik_client_secret,
            base_url=settings.mcp_base_url,
            require_authorization_consent="external",
        )
        logger.info("Authentik OAuth enabled (slug=%s)", settings.authentik_app_slug)

    if provider and not verifiers:
        return provider
    if verifiers:
        logger.info("API key auth enabled%s", " + OAuth (MultiAuth)" if provider else "")
        return MultiAuth(server=provider, verifiers=verifiers)
    return None
