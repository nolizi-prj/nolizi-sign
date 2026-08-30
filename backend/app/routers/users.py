"""User routes: list (for signer pickers and the admin console), create, and update.

List and create are gated by ``require_sender`` (admins, or any internal
user with ``can_send``) — picking signers and provisioning signer-only
accounts are part of the same send flow already opened to non-admin
senders in routers/templates.py and routers/submissions.py. Update is also
``require_sender``-gated but is two-tier from there: the admin-flag/can_send
toggles stay admin-only, while correcting an external signer's name/email
is open to any sender (see ``update_user``).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import email_domain_allowed, get_settings, placeholder_name_from_email, require_sender
from app.config import Settings
from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _sender: User = Depends(require_sender),
) -> list[User]:
    """List all users, ordered by name — for signer pickers and the admin console."""
    return list(db.scalars(select(User).order_by(User.name)))


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _sender: User = Depends(require_sender),
) -> User:
    """Provision a user by email so they can be picked as a signer before ever logging in.

    Internal-domain users (ALLOWED_EMAIL_DOMAINS, default pumasi.ai) start with
    a placeholder name derived from the email's local part ("jane.doe@..." -> "Jane Doe");
    their first login overwrites it with the real display name, since login matches users
    by email (see app/auth.py).

    External-domain users (anyone else) are provisioned as read-only signers who never
    log in. They require an explicit name to be supplied, since they can't correct a
    placeholder on first login. If the email already belongs to a user, that user is
    returned unchanged with a 200.
    """
    existing = db.scalars(select(User).where(User.email == payload.email)).one_or_none()
    if existing is not None:
        response.status_code = 200
        return existing

    is_external = not email_domain_allowed(payload.email, settings)
    if is_external and not payload.name:
        # The certificate and name-field stamping need a real display name,
        # and an external signer never logs in to correct a placeholder.
        raise HTTPException(status_code=422, detail="External signer requires a name")

    user = User(
        email=payload.email,
        name=payload.name or placeholder_name_from_email(payload.email),
        is_admin=False,
        is_external=is_external,
        # Externals can never send (require_sender excludes them regardless);
        # storing false keeps the admin user list's disabled toggle honest.
        can_send=not is_external,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> User:
    """Two-tier update: admin-flag/can_send toggles, and/or external-signer
    contact correction. Only fields present in the payload
    (``exclude_unset=True``) are touched, so a request can do either or both.

    ``is_admin``/``can_send``: the caller must be an admin (403 otherwise).
    409 if the caller is trying to remove their own admin flag — an admin
    always needs at least one other admin's help to be demoted, so nobody
    can accidentally lock themselves (and, if they're the last admin,
    everyone) out of the admin console.

    ``name``/``email``: correcting an external signer's contact info after a
    typo. Any sender may do this, but only on a target user with
    ``is_external`` set (403 otherwise — this applies to internal targets
    even for admins, since internal identity comes from SSO/login, not a
    manual edit). The new email must be unique (409) and must resolve to an
    external domain per ``email_domain_allowed`` (422) — an external signer
    must stay external.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    fields = payload.model_dump(exclude_unset=True)

    if "is_admin" in fields or "can_send" in fields:
        if not sender.is_admin:
            raise HTTPException(status_code=403, detail="Admin required")
        # Externals can never send or administrate — require_sender/require_admin
        # would ignore the flags anyway, but a stored true renders a
        # misleadingly "on" toggle in the admin user list.
        if user.is_external and (fields.get("is_admin") or fields.get("can_send")):
            raise HTTPException(status_code=422, detail="External signers can never send or be admins")
        if "is_admin" in fields:
            if user.id == sender.id and not fields["is_admin"]:
                raise HTTPException(status_code=409, detail="Cannot remove your own admin flag")
            user.is_admin = fields["is_admin"]
        if "can_send" in fields:
            user.can_send = fields["can_send"]

    if "name" in fields or "email" in fields:
        if not user.is_external:
            raise HTTPException(status_code=403, detail="Only external users' contact info can be edited")
        if "email" in fields:
            new_email = fields["email"]
            if email_domain_allowed(new_email, settings):
                raise HTTPException(status_code=422, detail="Use an external email address")
            collision = db.scalars(select(User).where(User.email == new_email, User.id != user.id)).one_or_none()
            if collision is not None:
                raise HTTPException(status_code=409, detail="Email already in use")
            user.email = new_email
        if "name" in fields:
            user.name = fields["name"]

    db.commit()
    db.refresh(user)
    return user
