"""Session cookies, auth dependencies, and claims-to-user upsert logic.

Three itsdangerous ``URLSafeTimedSerializer`` cookies are used:

- ``sign_session`` (salt ``"sign-session"``): holds ``{"uid": user_id}`` for
  12 hours. Set on successful login (Entra callback or dev bypass), read by
  ``current_user``.
- ``sign_authflow`` (salt ``"sign-authflow"``): holds the MSAL
  ``initiate_auth_code_flow`` dict plus the post-login ``next`` path, for the
  10-minute round trip between ``/api/auth/login`` and ``/api/auth/callback``.
  Kept separate from the session cookie/salt so the two can never be
  confused for one another even though they share the same secret key.
- ``sign_signer`` (salt ``"sign-signer"``): holds ``{"sid": submitter_id,
  "uid": user_id}`` for 4 hours. Set when granting external signers access
  to a specific submission, read by ``signer_identity`` to grant scoped
  access. ``uid`` is the submitter row's ``user_id`` *at the moment the
  cookie was issued* — every read re-checks it against the submitter row's
  *current* ``user_id`` (not just ``sid``), because ``replace_submitter``
  can swap who a submitter row belongs to without changing the row's id:
  without the ``uid`` check, the replaced (wrong) signer's still-valid
  cookie would keep opening and could complete the envelope as the new
  signer. Cookies signed before ``uid`` existed (or otherwise missing it)
  are rejected outright rather than falling back to sid-only trust.

A fourth serializer (salt ``"sign-magiclink"``) signs emailed magic-link
login tokens rather than a cookie — same secret, distinct salt, for the
same non-confusion reason.
"""

import re

from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.models import User

SESSION_COOKIE_NAME = "sign_session"
SESSION_SALT = "sign-session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60

AUTHFLOW_COOKIE_NAME = "sign_authflow"
AUTHFLOW_SALT = "sign-authflow"
AUTHFLOW_MAX_AGE_SECONDS = 10 * 60

MAGICLINK_SALT = "sign-magiclink"
MAGIC_LINK_MAX_AGE_SECONDS = 15 * 60

SIGNER_COOKIE_NAME = "sign_signer"
SIGNER_SALT = "sign-signer"
SIGNER_MAX_AGE_SECONDS = 4 * 60 * 60


def session_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Return the itsdangerous serializer used for the session cookie."""
    return URLSafeTimedSerializer(settings.session_secret, salt=SESSION_SALT)


def authflow_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Return the itsdangerous serializer used for the transient auth-flow cookie."""
    return URLSafeTimedSerializer(settings.session_secret, salt=AUTHFLOW_SALT)


def magiclink_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Return the itsdangerous serializer used for email magic-link tokens."""
    return URLSafeTimedSerializer(settings.session_secret, salt=MAGICLINK_SALT)


def signer_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Serializer for the external-signer cookie (distinct salt, same secret)."""
    return URLSafeTimedSerializer(settings.session_secret, salt=SIGNER_SALT)


def _cookie_is_secure(settings: Settings) -> bool:
    return settings.app_base_url.startswith("https")


def set_session_cookie(response: Response, user_id: int, settings: Settings) -> None:
    """Sign and set the ``sign_session`` cookie for ``user_id`` on ``response``."""
    token = session_serializer(settings).dumps({"uid": user_id})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_is_secure(settings),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the ``sign_session`` cookie on ``response``."""
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def set_signer_cookie(response: Response, submitter_id: int, user_id: int, settings: Settings) -> None:
    """Set the scoped ``sign_signer`` cookie granting access to one submitter, for one user.

    ``user_id`` is baked into the signed payload alongside ``submitter_id``
    so ``signer_identity`` can catch a submitter row that got reassigned to
    someone else (``replace_submitter``) after this cookie was issued — see
    the module docstring.
    """
    token = signer_serializer(settings).dumps({"sid": submitter_id, "uid": user_id})
    response.set_cookie(
        key=SIGNER_COOKIE_NAME,
        value=token,
        max_age=SIGNER_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_is_secure(settings),
        samesite="lax",
        path="/",
    )


def signer_identity(request: Request, settings: Settings) -> tuple[int, int] | None:
    """``(submitter_id, user_id)`` from a valid ``sign_signer`` cookie, else None (never raises).

    A cookie without a ``uid`` claim (expired-format or tampered) is treated
    the same as no cookie at all — callers must never fall back to trusting
    ``sid`` alone, since that's exactly what would let a replaced signer's
    old cookie keep working. Callers still must compare both fields against
    the submitter row's *current* state; this function only decodes the
    cookie, it doesn't consult the database.
    """
    token = request.cookies.get(SIGNER_COOKIE_NAME)
    if not token:
        return None
    try:
        data = signer_serializer(settings).loads(token, max_age=SIGNER_MAX_AGE_SECONDS)
        sid = data["sid"]
        uid = data["uid"]
    except (BadSignature, SignatureExpired, KeyError, TypeError):
        return None
    if not isinstance(sid, int) or not isinstance(uid, int):
        return None
    return sid, uid


def get_settings(request: Request) -> Settings:
    """Return the Settings instance the app was built with (see ``create_app``)."""
    return request.app.state.settings


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the logged-in User from the session cookie, or raise 401."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        data = session_serializer(settings).loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        uid = data["uid"]
    except (BadSignature, SignatureExpired, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc

    user = db.get(User, uid)
    if user is None or user.is_external:
        # External signers never hold app sessions — their only access path
        # is the sign_signer cookie (see routers/signing.py).
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """``current_user``, but None instead of 401 — for routes that also accept the signer cookie."""
    try:
        return current_user(request, db, settings)
    except HTTPException:
        return None


def require_admin(user: User = Depends(current_user)) -> User:
    """Pass through ``user`` if they are an admin, else raise 403."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")
    return user


def require_sender(user: User = Depends(current_user)) -> User:
    """Pass through ``user`` if they may send (admin, or can_send and internal), else raise 403."""
    if not (user.is_admin or (user.can_send and not user.is_external)):
        raise HTTPException(status_code=403, detail="Sender access required")
    return user


def email_domain_allowed(email: str, settings: Settings) -> bool:
    """True when ``email``'s domain is in ALLOWED_EMAIL_DOMAINS (False for addresses with no '@').

    The single source of truth for the "who can have an account here" gate —
    used by magic-link login (request + callback) and by admin signer
    provisioning (POST /api/users).
    """
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    return domain in settings.allowed_email_domains_list


def placeholder_name_from_email(email: str) -> str:
    """Display-name placeholder for a user provisioned from a bare email ("jane.doe@…" → "Jane Doe").

    Their first real login overwrites it (login matches users by email), so
    this only has to be presentable, not authoritative.
    """
    local_part = email.split("@", 1)[0]
    return re.sub(r"[._-]+", " ", local_part).strip().title() or email


def upsert_user(db: Session, *, email: str, name: str, entra_oid: str | None, settings: Settings) -> User:
    """Create or update the User for ``email`` (lowercased) and return it.

    On create, ``is_admin`` is set from ``settings.admin_emails_list``. On an
    existing user, name/entra_oid are refreshed and ``is_admin`` is flipped
    to True (never back to False) when the email is currently admin-listed —
    so removing someone from ADMIN_EMAILS does not silently demote them on
    next login; that's an explicit admin action outside this flow.
    """
    normalized_email = email.strip().lower()
    is_admin_email = normalized_email in settings.admin_emails_list

    user = db.query(User).filter(User.email == normalized_email).one_or_none()
    if user is None:
        user = User(email=normalized_email, name=name, entra_oid=entra_oid, is_admin=is_admin_email)
        db.add(user)
    else:
        user.name = name
        if entra_oid:
            user.entra_oid = entra_oid
        if is_admin_email and not user.is_external:
            user.is_admin = True

    db.commit()
    db.refresh(user)
    return user


def upsert_user_from_claims(db: Session, claims: dict, settings: Settings) -> User:
    """Validate the Entra ``tid`` claim and upsert a User from the ID token claims.

    Raises 403 if the token's tenant doesn't match ``settings.ms_tenant_id``.
    """
    if claims.get("tid") != settings.ms_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    email = claims.get("preferred_username") or claims.get("email")
    name = claims.get("name") or email
    entra_oid = claims.get("oid")
    user = upsert_user(db, email=email, name=name, entra_oid=entra_oid, settings=settings)
    if user.is_external:
        # Tenant-gated Entra login is proof of employment: a contractor who
        # got hired keeps their row (and signing history) and becomes internal.
        user.is_external = False
        db.commit()
        db.refresh(user)
    return user
