"""Microsoft Graph mail delivery (client-credentials / app-only auth).

``send`` is the sole public entry point. It never raises to callers — any
failure (missing config, no token, HTTP error after retries, transport
error) is logged and results in a ``False`` return, so a mail outage can
never turn into a 500 for the request that triggered it (submission
creation, signing completion, reminders, the daily job).

**Auth**: the token acquisition machinery (MSAL ``ConfidentialClientApplication``,
client-credentials flow, scope ``https://graph.microsoft.com/.default``) lives
in ``app.graph`` and is shared with ``app.sharepoint`` — an MSAL app object
is built once per distinct ``(tenant, client_id, client_secret)`` triple and
cached at module level, so both mail and archiving reuse the same token cache.

**Test seam**: two independent injection points, since token acquisition
(via MSAL, which does its own HTTP under the hood) and the actual Graph
``sendMail`` call (via this module's own ``httpx.Client``) are different
HTTP stacks:

- ``transport``: an optional ``httpx.BaseTransport`` (e.g.
  ``httpx.MockTransport``) forwarded to the ``httpx.Client`` used for the
  Graph API call. This is the seam the brief calls out explicitly.
- ``app.mailer._acquire_token``: a module-level *rebinding* of ``app.graph.acquire_token``
  that tests monkeypatch directly (``monkeypatch.setattr(mailer, "_acquire_token", lambda s: "tok")``)
  to bypass real MSAL/network token acquisition entirely. There is no
  ``transport``-style hook into MSAL itself, so this is the only practical
  way to keep tests offline.
- ``sleep``: an optional callable (default ``time.sleep``) so retry-path
  tests don't actually wait 1s/4s/16s in real time.

**Never logged**: message bodies, recipient addresses, subjects, or
tokens. Failure logs here are generic (status code / exception type only);
callers with more context (``app.notifications``) log submission/submitter
ids on top of that.
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable

import httpx

from app.config import Settings
from app.graph import acquire_token as _acquire_token

logger = logging.getLogger(__name__)

GRAPH_SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"

# 1 initial attempt + 3 retries, sleeping this long before each retry.
RETRY_DELAYS_SECONDS: tuple[float, ...] = (1.0, 4.0, 16.0)


def _build_message_body(
    to: list[str],
    subject: str,
    html: str,
    attachments: list[tuple[str, bytes, str]],
) -> dict:
    message: dict = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html},
        "toRecipients": [{"emailAddress": {"address": address}} for address in to],
    }
    if attachments:
        message["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": content_type,
                "contentBytes": base64.b64encode(data).decode("ascii"),
            }
            for name, data, content_type in attachments
        ]
    return {"message": message, "saveToSentItems": True}


def send(
    settings: Settings,
    to: list[str],
    subject: str,
    html: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Send an HTML email via Graph ``sendMail``. Returns ``True`` on success, never raises.

    ``to`` is a list of recipient email addresses; ``attachments`` is a
    list of ``(filename, bytes, content_type)`` triples, each sent as a
    Graph ``fileAttachment`` with that content type.

    Retries on HTTP 429, any 5xx, and ``httpx`` transport errors: up to 3
    retries (4 attempts total) with 1s/4s/16s backoff between them. Any
    other HTTP status (a non-retryable 4xx) fails immediately without
    retrying. Missing mail configuration (tenant/client/secret/sender) or a
    failed token acquisition also returns ``False`` immediately — no
    network call to Graph is attempted in that case.
    """
    if not (settings.ms_tenant_id and settings.ms_client_id and settings.ms_client_secret and settings.mail_sender):
        logger.warning("Mail not configured (missing tenant/client/secret/sender); skipping send")
        return False

    if not to:
        logger.warning("mailer.send called with no recipients; skipping")
        return False

    token = _acquire_token(settings)
    if not token:
        return False

    body = _build_message_body(to, subject, html, attachments or [])
    url = GRAPH_SEND_MAIL_URL.format(sender=settings.mail_sender)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    client_kwargs = {"transport": transport} if transport is not None else {}
    with httpx.Client(timeout=30.0, **client_kwargs) as client:
        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            if attempt > 0:
                sleep(RETRY_DELAYS_SECONDS[attempt - 1])

            try:
                response = client.post(url, json=body, headers=headers)
            except httpx.TransportError:
                logger.warning("Graph sendMail transport error on attempt %d", attempt + 1)
                continue

            if response.status_code < 300:
                return True

            if response.status_code == 429 or response.status_code >= 500:
                logger.warning("Graph sendMail returned %d on attempt %d", response.status_code, attempt + 1)
                continue

            logger.error("Graph sendMail returned non-retryable status %d", response.status_code)
            return False

    logger.error("Graph sendMail failed after %d attempts", len(RETRY_DELAYS_SECONDS) + 1)
    return False
