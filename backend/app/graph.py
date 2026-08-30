"""Shared Microsoft Graph app-only auth (client-credentials flow).

An MSAL ``ConfidentialClientApplication`` is built once per distinct
``(tenant, client_id, client_secret)`` triple and cached at module level —
MSAL's app object owns its own token cache, so both mail sending
(``app.mailer``) and SharePoint archiving (``app.sharepoint``) reuse the
same token instead of re-authenticating per call.

Never logs tokens; a failed acquisition logs the MSAL error code only.
"""

from __future__ import annotations

import logging

import msal

from app.config import Settings

logger = logging.getLogger(__name__)

GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]

_msal_apps: dict[tuple[str, str, str], msal.ConfidentialClientApplication] = {}


def _get_msal_app(settings: Settings) -> msal.ConfidentialClientApplication:
    """Return the cached MSAL app for this tenant/client, building it on first use."""
    key = (settings.ms_tenant_id, settings.ms_client_id, settings.ms_client_secret)
    app = _msal_apps.get(key)
    if app is None:
        app = msal.ConfidentialClientApplication(
            settings.ms_client_id,
            authority=f"https://login.microsoftonline.com/{settings.ms_tenant_id}",
            client_credential=settings.ms_client_secret,
        )
        _msal_apps[key] = app
    return app


def acquire_token(settings: Settings) -> str | None:
    """Acquire (or reuse from MSAL's own cache) an app-only Graph access token."""
    app = _get_msal_app(settings)
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)
    token = result.get("access_token")
    if not token:
        logger.error("Failed to acquire Graph access token: %s", result.get("error", "unknown_error"))
    return token
