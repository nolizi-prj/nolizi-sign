"""Auth routes: Entra ID login/callback, email magic links, logout, dev bypass.

The login/callback pair is a standard MSAL confidential-client auth-code
flow. ``initiate_auth_code_flow`` builds the redirect URL and a flow dict
that must be handed back unchanged to ``acquire_token_by_auth_code_flow`` on
the way back in; since HTTP is stateless we stash that flow dict (plus the
``next`` path to return to) in a short-lived signed cookie rather than
server-side session storage.
"""

import html
import time
from urllib.parse import quote, urlparse

import msal
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import mailer
from app.auth import (
    AUTHFLOW_COOKIE_NAME,
    AUTHFLOW_MAX_AGE_SECONDS,
    MAGIC_LINK_MAX_AGE_SECONDS,
    authflow_serializer,
    clear_session_cookie,
    current_user,
    email_domain_allowed,
    get_settings,
    magiclink_serializer,
    placeholder_name_from_email,
    set_session_cookie,
    upsert_user,
    upsert_user_from_claims,
)
from app.config import Settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _is_safe_relative_path(path: str) -> bool:
    """Return whether ``path`` is a same-origin relative path (no scheme/netloc).

    Rejects backslashes outright rather than just leading ``//``: browsers
    apply the WHATWG "backslash trick" and normalize a leading ``/\\`` (or
    ``\\/``) to ``//``, turning what looks like a relative path into a
    protocol-relative one pointing at an attacker's host. Relying on
    ``urlparse`` alone doesn't catch this since Python's URL parser doesn't
    do that normalization.
    """
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return False
    parsed = urlparse(path)
    return not parsed.scheme and not parsed.netloc


def _msal_app(settings: Settings) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        settings.ms_client_id,
        authority=f"https://login.microsoftonline.com/{settings.ms_tenant_id}",
        client_credential=settings.ms_client_secret,
    )


def _user_out(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "is_external": user.is_external,
        # Effective send permission, not the raw column: admins can always
        # send, and external users never can regardless of the column.
        "can_send": user.is_admin or (user.can_send and not user.is_external),
    }


@router.get("/login")
def login(
    next_path: str = Query("/", alias="next"),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Redirect to Entra for sign-in, stashing the MSAL flow + ``next`` in a signed cookie."""
    if not _is_safe_relative_path(next_path):
        raise HTTPException(status_code=400, detail="next must be a relative path")

    flow = _msal_app(settings).initiate_auth_code_flow(
        scopes=["User.Read"],
        redirect_uri=f"{settings.app_base_url}/api/auth/callback",
    )

    response = RedirectResponse(url=flow["auth_uri"], status_code=302)
    token = authflow_serializer(settings).dumps({"flow": flow, "next": next_path})
    response.set_cookie(
        key=AUTHFLOW_COOKIE_NAME,
        value=token,
        max_age=AUTHFLOW_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.app_base_url.startswith("https"),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/callback")
def callback(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Exchange the auth code, validate the tenant, upsert the user, and start a session."""
    raw_flow_cookie = request.cookies.get(AUTHFLOW_COOKIE_NAME)
    if not raw_flow_cookie:
        raise HTTPException(status_code=400, detail="Missing or expired auth flow")

    try:
        flow_data = authflow_serializer(settings).loads(raw_flow_cookie, max_age=AUTHFLOW_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=400, detail="Missing or expired auth flow") from exc

    result = _msal_app(settings).acquire_token_by_auth_code_flow(flow_data["flow"], dict(request.query_params))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("error_description", result["error"]))

    user = upsert_user_from_claims(db, result["id_token_claims"], settings)

    response = RedirectResponse(url=flow_data.get("next", "/"), status_code=302)
    response.delete_cookie(AUTHFLOW_COOKIE_NAME, path="/")
    set_session_cookie(response, user.id, settings)
    return response


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    """Clear the session cookie."""
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict[str, object]:
    """Return the current user's profile."""
    return _user_out(user)


class DevLoginRequest(BaseModel):
    """Body for POST /api/auth/dev-login."""

    email: str
    name: str


@router.post("/dev-login")
def dev_login(
    payload: DevLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Dev-only login bypass: upsert a user by email/name and set a session cookie.

    404s (rather than 403) when DEV_AUTH_BYPASS is unset, so the route's
    existence isn't revealed in environments where it should be off.
    """
    if not settings.dev_auth_bypass:
        raise HTTPException(status_code=404)

    user = upsert_user(db, email=payload.email, name=payload.name, entra_oid=None, settings=settings)
    set_session_cookie(response, user.id, settings)
    return _user_out(user)


MAGIC_LINK_RATE_LIMIT = 3
MAGIC_LINK_RATE_WINDOW_SECONDS = 15 * 60

# Same visual style as notifications._BUTTON_STYLE (private to that module).
MAGIC_LINK_BUTTON_STYLE = (
    "display:inline-block;padding:10px 20px;background:#1C3A62;color:#ffffff;"
    "text-decoration:none;border-radius:6px;font-family:sans-serif;"
)

# In-process rate-limit state: normalized email -> recent send times
# (time.time()). Fine for a single-process uvicorn deployment; revisit if the
# app ever runs multiple workers.
_email_login_sends: dict[str, list[float]] = {}


class EmailLoginRequest(BaseModel):
    """Body for POST /api/auth/email/request."""

    email: str
    next: str | None = None


@router.post("/email/request")
def email_login_request(
    payload: EmailLoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    """Email a magic sign-in link to an allowed-domain address.

    Always returns a generic ``{"ok": true}`` for ineligible domains and
    rate-limited addresses so the endpoint doesn't reveal who can log in;
    502 only when a send was actually attempted and the mailer failed.
    """
    email = payload.email.strip().lower()
    if not email_domain_allowed(email, settings):
        return {"ok": True}

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None and existing.is_external:
        return {"ok": True}  # same silent shape as an ineligible domain

    now = time.time()
    recent = [ts for ts in _email_login_sends.get(email, []) if now - ts < MAGIC_LINK_RATE_WINDOW_SECONDS]
    if len(recent) >= MAGIC_LINK_RATE_LIMIT:
        _email_login_sends[email] = recent
        return {"ok": True}

    next_path = payload.next if payload.next and _is_safe_relative_path(payload.next) else "/"
    token = magiclink_serializer(settings).dumps({"email": email, "next": next_path})
    link = f"{settings.app_base_url}/api/auth/email/callback?token={quote(token)}"
    body = (
        "<p>Use the button below to sign in to Pumasi Sign. "
        "The link expires in 15 minutes and can be used once.</p>"
        f'<p><a href="{html.escape(link)}" style="{MAGIC_LINK_BUTTON_STYLE}">Sign in</a></p>'
        "<p>If you didn't request this, you can ignore this email.</p>"
    )
    if not mailer.send(settings, [email], "Your Pumasi Sign sign-in link", body):
        raise HTTPException(status_code=502, detail="Could not send the sign-in email")

    recent.append(now)
    _email_login_sends[email] = recent
    return {"ok": True}


_EXPIRED_REDIRECT = "/login?error=expired"


@router.get("/email/callback")
def email_login_callback(
    token: str = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Verify a magic-link token, enforce single use, and start a session.

    Any failure (bad signature, expired, replayed, domain no longer allowed)
    redirects to the login page with a generic "expired" notice — the token
    came from an email link, so a JSON error would be user-hostile and a
    specific one would leak which check failed.
    """
    try:
        data, issued_at = magiclink_serializer(settings).loads(
            token,
            max_age=MAGIC_LINK_MAX_AGE_SECONDS,
            return_timestamp=True,
        )
        email = data["email"]
    except (BadSignature, SignatureExpired, KeyError, TypeError):
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    if not email_domain_allowed(email, settings):
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None and existing.is_external:
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    if existing is not None and existing.email_login_min_iat is not None and issued_at <= existing.email_login_min_iat:
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    name = existing.name if existing is not None else placeholder_name_from_email(email)
    user = upsert_user(db, email=email, name=name, entra_oid=None, settings=settings)
    user.email_login_min_iat = issued_at
    db.commit()

    next_path = data.get("next") or "/"
    if not _is_safe_relative_path(next_path):
        next_path = "/"

    response = RedirectResponse(url=next_path, status_code=302)
    set_session_cookie(response, user.id, settings)
    return response
