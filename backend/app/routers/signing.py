"""Signing routes: the submitter-facing "sign this document" flow.

Three routes, all keyed by ``submitter_id`` (not ``submission_id``) and
authorized identically: 404 if the ``Submitter`` row doesn't exist, 403
unless the caller is either the logged-in internal user who owns this
submitter row, or holds a ``sign_signer`` cookie scoped to this exact
submitter (see ``SigningIdentity``/``signing_identity`` below) — this is a
personal signing link, not something a sender/admin can drive on someone
else's behalf.

- ``GET /api/sign/{submitter_id}`` — fetch what the submitter needs to
  render their signing page; flips ``pending`` -> ``opened`` (+ audit) on
  first view.
- ``POST /api/sign/{submitter_id}/signature`` — upload/store a signature
  image, reusable across fields (and across submissions) for that user.
- ``POST /api/sign/{submitter_id}/complete`` — submit field values, mark
  the submitter done, and (if they're the last one) trigger
  ``completion.finalize``.
"""

import base64
import binascii
import hashlib
import hmac
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import audit, completion, mailer, notifications, sharepoint
from app.auth import get_settings, optional_user, set_signer_cookie, signer_identity
from app.config import Settings
from app.db import get_db
from app.http_utils import client_ip
from app.models import Attachment, Signature, Submission, Submitter, User
from app.schemas import (
    EMAIL_RE,
    AttachmentOut,
    FieldDef,
    SignatureImageIn,
    SignatureOut,
    SignCompleteIn,
    SignDeclineIn,
    SignerViewOut,
    SignSubmissionBrief,
    SignTemplateBrief,
    SignTokenVerifyIn,
    SignTokenVerifyOut,
    SignTokenViewOut,
)
from app.stamping import trimmed_signature
from app.storage import FileStorage, get_storage

router = APIRouter(prefix="/api/sign", tags=["signing"])

MAX_SIGNATURE_BYTES = 1024 * 1024
PNG_DATA_URL_PREFIX = "data:image/png;base64,"
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"
MAX_TEXT_LENGTH = 500

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
_ATTACHMENT_CHUNK_BYTES = 1024 * 1024
# Accepted attachment formats, sniffed by magic bytes (the client-supplied
# content type is advisory at best): (magic, extension, content type).
_ATTACHMENT_MAGIC: list[tuple[bytes, str, str]] = [
    (b"%PDF", "pdf", "application/pdf"),
    (PNG_MAGIC_BYTES, "png", "image/png"),
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
]


@dataclass
class SigningIdentity:
    """Who is calling a /api/sign route: a logged-in internal user, an
    email-verified external signer (signer cookie), or both. At least one
    of the two fields is set — the dependency 401s otherwise.

    ``cookie_submitter_id``/``cookie_user_id`` are the ``sid``/``uid`` the
    ``sign_signer`` cookie claims — both are None together (cookie absent
    or invalid) or both set together (never one without the other), since
    ``signer_identity`` rejects any cookie missing ``uid``. A caller must
    still check ``cookie_user_id`` against the target submitter's *current*
    ``user_id`` — see ``_get_submitter_authorized`` — not just ``sid``
    against its id, or a signer swapped out by ``replace_submitter`` could
    keep using their old cookie as the new signer.
    """

    user: User | None
    cookie_submitter_id: int | None
    cookie_user_id: int | None


def signing_identity(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SigningIdentity:
    user = optional_user(request, db, settings)
    cookie = signer_identity(request, settings)
    if user is None and cookie is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sid, uid = cookie if cookie is not None else (None, None)
    return SigningIdentity(user=user, cookie_submitter_id=sid, cookie_user_id=uid)


# --- External token flow -----------------------------------------------------
#
# Public (unauthenticated) endpoints that let an external signer, who has no
# Pumasi account/session, use their emailed link (`access_uid`) to prove
# control of their own mailbox via a one-time code, and in exchange get a
# `sign_signer` cookie scoped to that one submitter — see app/auth.py.

VERIFICATION_CODE_TTL_SECONDS = 10 * 60
VERIFICATION_MAX_ATTEMPTS = 5
CODE_SEND_LIMIT = 3
CODE_SEND_IP_LIMIT = 10
CODE_SEND_WINDOW_SECONDS = 15 * 60

# In-process rate-limit state (single-process deployment — same trade-off as
# the magic-link limiter in routers/auth.py).
_code_sends_by_uid: dict[str, list[float]] = {}
_code_sends_by_ip: dict[str, list[float]] = {}


def _over_limit(history: dict[str, list[float]], key: str, limit: int, now: float) -> bool:
    recent = [ts for ts in history.get(key, []) if now - ts < CODE_SEND_WINDOW_SECONDS]
    if len(recent) >= limit:
        history[key] = recent
        return True
    recent.append(now)
    history[key] = recent
    return False


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _get_submitter_by_access_uid(db: Session, access_uid: str) -> Submitter:
    submitter = db.scalars(
        select(Submitter)
        .options(
            selectinload(Submitter.user),
            selectinload(Submitter.submission).selectinload(Submission.template),
        )
        .where(Submitter.access_uid == access_uid),
    ).one_or_none()
    if submitter is None:
        raise HTTPException(status_code=404, detail="Unknown signing link")
    if submitter.submission.status == "draft":
        # Same rule as _get_submitter_authorized: an unsent draft's link
        # (never emailed, but the secret exists) must not resolve.
        raise HTTPException(status_code=404, detail="Unknown signing link")
    return submitter


def _token_status(submitter: Submitter) -> str:
    submission = submitter.submission
    if submission.status in ("cancelled", "declined", "completed"):
        return submission.status
    if submitter.status == "completed":
        return "already_signed"
    return "open"


# Statuses in which the code round-trip is still allowed: signing ("open"),
# or retrieving the signed PDF a party is entitled to ("already_signed" /
# "completed" — files.py serves signed-pdf over the scoped cookie). Voided
# and declined envelopes have no executed document to hand out.
_CODE_ALLOWED_STATUSES = ("open", "already_signed", "completed")


@router.get("/token/{access_uid}", response_model=SignTokenViewOut)
def get_token_view(access_uid: str, db: Session = Depends(get_db)) -> SignTokenViewOut:
    """Public landing data for an external sign link: just enough to render
    "we'll email a code to e***@vendor.com" — nothing signable is exposed
    until the code round-trip proves mailbox control."""
    submitter = _get_submitter_by_access_uid(db, access_uid)
    submission = submitter.submission
    sender = db.get(User, submission.created_by)
    return SignTokenViewOut(
        status=_token_status(submitter),
        title=submission.title,
        sender_name=sender.name if sender else "Someone",
        masked_email=_mask_email(submitter.user.email),
    )


@router.post("/token/{access_uid}/request-code")
def request_verification_code(
    access_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Email a fresh 6-digit code to the submitter's own address."""
    submitter = _get_submitter_by_access_uid(db, access_uid)
    if _token_status(submitter) not in _CODE_ALLOWED_STATUSES:
        raise HTTPException(status_code=409, detail="This envelope is no longer open for signing")

    now = time.monotonic()
    ip = client_ip(request) or "unknown"
    if _over_limit(_code_sends_by_uid, access_uid, CODE_SEND_LIMIT, now) or _over_limit(
        _code_sends_by_ip,
        ip,
        CODE_SEND_IP_LIMIT,
        now,
    ):
        raise HTTPException(status_code=429, detail="Too many code requests; please try again later")

    code = f"{secrets.randbelow(1_000_000):06d}"
    submitter.verification_code_hash = hashlib.sha256(code.encode()).hexdigest()
    submitter.verification_code_expires_at = datetime.now(UTC) + timedelta(seconds=VERIFICATION_CODE_TTL_SECONDS)
    submitter.verification_attempts = 0
    db.commit()

    body = (
        f"<p>Your Pumasi Sign verification code is:</p>"
        f'<p style="font-size:24px;font-weight:bold;letter-spacing:4px;font-family:monospace">{code}</p>'
        "<p>It expires in 10 minutes. If you didn't request this, you can ignore this email.</p>"
    )
    sent = mailer.send(settings, [submitter.user.email], "Your Pumasi Sign verification code", body)
    if not sent and not settings.dev_auth_bypass:
        raise HTTPException(status_code=502, detail="Could not send the verification email")

    result: dict = {"ok": True}
    if settings.dev_auth_bypass:
        # e2e-only escape hatch; DEV_AUTH_BYPASS is never set in production. A
        # dev/e2e environment normally has no real mail credentials configured
        # (mailer.send always returns False there), so the whole point of this
        # hatch is to hand back the code even when the send itself failed —
        # tests still can't read the signer's mailbox either way.
        result["dev_code"] = code
    return result


@router.post("/token/{access_uid}/verify", response_model=SignTokenVerifyOut)
def verify_code(
    access_uid: str,
    payload: SignTokenVerifyIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SignTokenVerifyOut:
    """Exchange a correct code for the scoped sign_signer cookie."""
    submitter = _get_submitter_by_access_uid(db, access_uid)
    if _token_status(submitter) not in _CODE_ALLOWED_STATUSES:
        raise HTTPException(status_code=409, detail="This envelope is no longer open for signing")
    if (
        submitter.verification_code_hash is None
        or submitter.verification_code_expires_at is None
        or datetime.now(UTC) >= submitter.verification_code_expires_at
    ):
        raise HTTPException(status_code=410, detail="Code expired or too many attempts — request a new one")

    submitted_hash = hashlib.sha256(payload.code.strip().encode()).hexdigest()
    if not hmac.compare_digest(submitted_hash, submitter.verification_code_hash):
        submitter.verification_attempts += 1
        if submitter.verification_attempts >= VERIFICATION_MAX_ATTEMPTS:
            submitter.verification_code_hash = None
            submitter.verification_code_expires_at = None
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect code")

    submitter.verification_code_hash = None
    submitter.verification_code_expires_at = None
    submitter.verification_attempts = 0
    db.commit()
    set_signer_cookie(response, submitter.id, submitter.user_id, settings)
    return SignTokenVerifyOut(submitter_id=submitter.id)


def _get_submitter_authorized(db: Session, submitter_id: int, identity: SigningIdentity) -> Submitter:
    submitter = db.scalars(
        select(Submitter)
        .options(
            selectinload(Submitter.submission).selectinload(Submission.template),
            selectinload(Submitter.submission).selectinload(Submission.submitters).selectinload(Submitter.user),
        )
        .where(Submitter.id == submitter_id),
    ).one_or_none()
    if submitter is None:
        raise HTTPException(status_code=404, detail="Submitter not found")
    if submitter.submission.status == "draft":
        # A draft was never sent — its would-be recipients must not discover
        # it exists, so this is a 404, not a 403/409.
        raise HTTPException(status_code=404, detail="Submitter not found")
    session_ok = identity.user is not None and submitter.user_id == identity.user.id
    # Both sid and uid must match the submitter row's *current* state — not
    # just sid — so a signer swapped out by replace_submitter can never use
    # their still-unexpired old cookie to act as whoever replaced them.
    cookie_ok = identity.cookie_submitter_id == submitter.id and identity.cookie_user_id == submitter.user_id
    if not (session_ok or cookie_ok):
        raise HTTPException(status_code=403, detail="Forbidden")
    if submitter.is_cc:
        # CC rows receive copies by email; there is nothing for them to view
        # or do on the signing routes.
        raise HTTPException(status_code=409, detail="This recipient receives a copy and has nothing to sign")
    return submitter


def _my_fields(submitter: Submitter) -> list[FieldDef]:
    template = submitter.submission.template
    return [FieldDef(**f) for f in template.fields if f["role"] == submitter.role]


def _expiry_passed(submission: Submission) -> bool:
    """Whether the envelope's deadline has passed. The daily sweep is what
    flips the status to "expired" (and notifies everyone); the signing routes
    use this to reject immediately in the window before the sweep runs."""
    return submission.expires_at is not None and submission.expires_at <= datetime.now(UTC)


def _is_my_turn(submitter: Submitter) -> bool:
    """Ordered signing: a submitter may sign only once every lower-order
    *signer* on the submission has completed (CC rows never gate routing)."""
    return all(
        peer.status == "completed"
        for peer in submitter.submission.submitters
        if not peer.is_cc and peer.order_index < submitter.order_index
    )


@router.get("/{submitter_id}", response_model=SignerViewOut)
def get_sign_view(
    submitter_id: int,
    request: Request,
    db: Session = Depends(get_db),
    identity: SigningIdentity = Depends(signing_identity),
) -> SignerViewOut:
    """Return what a submitter needs to render their signing page.

    On the first view (submitter ``pending`` and submission ``pending``),
    flips the submitter to ``opened``, records an ``opened`` audit event
    with the caller's IP, and commits — this route is a GET but performs
    that one side effect deliberately, per the task brief. The flip only
    happens once it's this signer's turn: a peek at a
    not-yet-routed envelope isn't an "opened" in the audit-trail sense
    (the certificate would otherwise show opens predating the sign request).
    """
    submitter = _get_submitter_authorized(db, submitter_id, identity)
    submission = submitter.submission
    template = submission.template

    if (
        submitter.status == "pending"
        and submission.status == "pending"
        and not _expiry_passed(submission)
        and _is_my_turn(submitter)
    ):
        submitter.status = "opened"
        ip = client_ip(request)
        audit.record(db, submission.id, "opened", actor_user_id=submitter.user_id, ip=ip, submitter_id=submitter.id)
        db.commit()
        db.refresh(submitter)

    my_fields = _my_fields(submitter)

    # The "use saved signature" shortcut hits GET /api/files/signature/{id},
    # which is session-only (see files.py) — pointless to hand a cookie-only
    # external caller an id it can never fetch.
    saved_signature_id = None
    if identity.user is not None:
        saved_signature_id = db.scalars(
            select(Signature.id)
            .where(Signature.user_id == submitter.user_id)
            .order_by(Signature.created_at.desc())
            .limit(1),
        ).first()

    # CC rows have role "" and never appear on the document — leaking their
    # names into every signer's view buys nothing.
    role_names = {s.role: s.user.name for s in submission.submitters if not s.is_cc}

    return SignerViewOut(
        submission=SignSubmissionBrief.model_validate(submission),
        template=SignTemplateBrief.model_validate(template),
        my_fields=[f.id for f in my_fields],
        my_status=submitter.status,
        my_turn=_is_my_turn(submitter),
        saved_signature_id=saved_signature_id,
        role_names=role_names,
        my_name=submitter.user.name,
    )


@router.post("/{submitter_id}/signature", response_model=SignatureOut)
def upload_signature(
    submitter_id: int,
    payload: SignatureImageIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    identity: SigningIdentity = Depends(signing_identity),
) -> SignatureOut:
    """Decode, validate, and store a signature image; return its new id.

    Rejected with 409 if this submitter already completed or the
    submission is no longer pending (cancelled/completed) — signing a new
    signature image at that point can't affect anything.
    """
    submitter = _get_submitter_authorized(db, submitter_id, identity)
    submission = submitter.submission

    if submitter.status == "completed" or submission.status != "pending":
        raise HTTPException(status_code=409, detail="Submission is not open for signing")

    if _expiry_passed(submission):
        raise HTTPException(status_code=409, detail="This envelope has expired and can no longer be signed")

    if not payload.image.startswith(PNG_DATA_URL_PREFIX):
        raise HTTPException(status_code=422, detail="image must be a data:image/png;base64, data URL")

    encoded = payload.image[len(PNG_DATA_URL_PREFIX) :]
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid base64 image data") from exc

    if not decoded.startswith(PNG_MAGIC_BYTES):
        raise HTTPException(status_code=422, detail="not a PNG image")

    if len(decoded) > MAX_SIGNATURE_BYTES:
        raise HTTPException(status_code=413, detail="Signature image exceeds the 1 MB limit")

    storage = get_storage(settings)
    key = f"signatures/{submitter.user_id}/{uuid.uuid4().hex}.png"
    # Store cropped to the ink (stamping applies the same trim defensively
    # for signatures saved before this existed) so previews and the
    # "use saved signature" dialog show the signature, not its margins.
    storage.save(key, trimmed_signature(decoded))

    signature = Signature(user_id=submitter.user_id, image_key=key)
    db.add(signature)
    db.commit()
    db.refresh(signature)

    return SignatureOut(signature_id=signature.id)


@router.post("/{submitter_id}/attachment", response_model=AttachmentOut)
async def upload_attachment(
    submitter_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    identity: SigningIdentity = Depends(signing_identity),
) -> AttachmentOut:
    """Store a signer's file for an ``attachment`` field; return its new id.

    PDF/PNG/JPEG only, sniffed by magic bytes, up to 10 MB. The row is
    scoped to this submitter — ``_validate_values`` rejects the id on any
    other envelope. Same 409 rules as signature upload: nothing to attach
    once this submitter completed or the envelope is closed/expired.
    """
    submitter = _get_submitter_authorized(db, submitter_id, identity)
    submission = submitter.submission

    if submitter.status == "completed" or submission.status != "pending":
        raise HTTPException(status_code=409, detail="Submission is not open for signing")

    if _expiry_passed(submission):
        raise HTTPException(status_code=409, detail="This envelope has expired and can no longer be signed")

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_ATTACHMENT_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail="Attachment exceeds the 10 MB limit")
        chunks.append(chunk)
    data = b"".join(chunks)

    match = next((m for m in _ATTACHMENT_MAGIC if data.startswith(m[0])), None)
    if match is None:
        raise HTTPException(status_code=422, detail="Attachment must be a PDF, PNG, or JPEG file")
    _magic, ext, content_type = match

    storage = get_storage(settings)
    key = f"attachments/{submitter.id}/{uuid.uuid4().hex}.{ext}"
    storage.save(key, data)

    attachment = Attachment(
        submitter_id=submitter.id,
        filename=(file.filename or f"attachment.{ext}")[:255],
        file_key=key,
        content_type=content_type,
        size=len(data),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return AttachmentOut(attachment_id=attachment.id, filename=attachment.filename)


def _validate_values(db: Session, submitter: Submitter, fields: list[FieldDef], values: dict) -> dict:
    """Validate ``values`` against ``fields`` (this submitter's fields) and return the stored dict.

    Raises 422 for: values keyed by a field id not in ``fields``; a
    required non-"name" field missing from ``values``; or any supplied
    value that doesn't match its field type's rule (signature -> int
    signature id owned by the submitter's user; date -> ISO ``YYYY-MM-DD``
    string; checkbox -> bool; text -> str, <=500 chars, matching the field's
    ``validation`` format when one is set; dropdown/radio -> one of the
    field's options; attachment -> int attachment id uploaded under this
    exact submitter row; name -> str, <=500 chars).
    "name" fields are never *required* (older clients omit them and stamping
    falls back to the account name) but a supplied value is validated.
    """
    user = submitter.user
    fields_by_id = {f.id: f for f in fields}

    unknown = sorted(set(values) - set(fields_by_id))
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown field id(s): {', '.join(unknown)}")

    for field in fields_by_id.values():
        if field.type == "name":
            continue
        if field.required and field.id not in values:
            raise HTTPException(status_code=422, detail=f"missing required field: {field.id}")

    validated: dict = {}
    for field_id, value in values.items():
        field = fields_by_id[field_id]

        if field.type in ("signature", "initials"):
            # Initials are captured and stored exactly like signatures — a
            # (smaller) PNG behind a Signature row — so both validate as an
            # owned signature id.
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"field {field_id}: {field.type} value must be an id")
            signature = db.get(Signature, value)
            if signature is None or signature.user_id != user.id:
                raise HTTPException(status_code=422, detail=f"field {field_id}: {field.type} not found or not yours")
            validated[field_id] = value

        elif field.type == "date":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"field {field_id}: date value must be a string")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"field {field_id}: date must be ISO YYYY-MM-DD") from exc
            validated[field_id] = value

        elif field.type == "checkbox":
            if not isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"field {field_id}: checkbox value must be a bool")
            validated[field_id] = value

        elif field.type == "text":
            if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
                raise HTTPException(
                    status_code=422,
                    detail=f"field {field_id}: text value must be a string of at most {MAX_TEXT_LENGTH} characters",
                )
            # Format rules apply to actual input only — an empty optional
            # field is "not filled in", not "an invalid email".
            stripped = value.strip()
            if stripped and field.validation == "email" and not re.fullmatch(EMAIL_RE, stripped):
                raise HTTPException(status_code=422, detail=f"field {field_id}: must be a valid email address")
            if stripped and field.validation == "number":
                try:
                    float(stripped)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=f"field {field_id}: must be a number") from exc
            validated[field_id] = value

        elif field.type in ("dropdown", "radio"):
            if not isinstance(value, str) or value not in (field.options or []):
                raise HTTPException(
                    status_code=422,
                    detail=f"field {field_id}: value must be one of the field's options",
                )
            validated[field_id] = value

        elif field.type == "attachment":
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"field {field_id}: attachment value must be an id")
            attachment = db.get(Attachment, value)
            if attachment is None or attachment.submitter_id != submitter.id:
                raise HTTPException(status_code=422, detail=f"field {field_id}: attachment not found or not yours")
            validated[field_id] = value

        else:  # "name" — optional override of the account name; validated like text when supplied
            if not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH:
                raise HTTPException(
                    status_code=422,
                    detail=f"field {field_id}: name value must be a string of at most {MAX_TEXT_LENGTH} characters",
                )
            validated[field_id] = value

    return validated


def _maybe_finalize(db: Session, submission_id: int, storage: FileStorage) -> completion.FinalizeOutcome:
    """Finalize ``submission_id`` if every submitter is completed, under a row lock.

    Thin wrapper around ``completion.finalize_if_ready`` — the row-locked,
    self-healing "is this submission ready?" check lives there now (shared
    with ``POST /api/submissions/{id}/retry-completion``) so that two
    different callers can never both decide independently to finalize the
    same submission. See that function's docstring for the full race
    analysis. Returns the outcome (unlike the old discard-it version) so
    ``complete_signing`` can decide, *after* its own commit, whether this
    request is the one that should send the completion email.
    """
    return completion.finalize_if_ready(db, submission_id, storage)


@router.post("/{submitter_id}/complete")
def complete_signing(
    submitter_id: int,
    payload: SignCompleteIn,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    identity: SigningIdentity = Depends(signing_identity),
) -> dict:
    """Validate and store this submitter's field values, marking them done.

    Idempotent: calling this again once already completed just returns
    ``{"already": true}`` rather than erroring (after a self-heal check —
    see ``_maybe_finalize``). A cancelled (or, in practice unreachable but
    checked anyway, already-completed) submission is rejected with 409. On
    success, ``_maybe_finalize`` is called — under a row lock, to close the
    concurrent-last-signer race — before the single commit at the end of
    this request.

    The completion email is sent *after* that commit, and only when this
    specific request is the one that actually finalized the submission
    (``FinalizeOutcome.FINALIZED`` *and* a post-commit re-check that
    ``submission.status == "completed"`` — ``FINALIZED`` alone doesn't mean
    stamping succeeded, see ``completion.finalize_if_ready``). This keeps
    the (potentially slow, Graph-backed) send off the row lock — see
    ``app.completion``'s module docstring.

    Serialized against a concurrent ``replace_submitter``: the unlocked
    ``_get_submitter_authorized`` call above can load a submitter that a
    concurrent replace then swaps to a different user before this request
    gets around to mutating it — mirroring ``decline_signing``, this takes
    the submission's ``SELECT ... FOR UPDATE`` lock (``replace_submitter``
    takes the same lock before it touches the submitter, so the two
    serialize on it) and then re-reads the submitter under
    ``populate_existing=True`` — without which the object loaded above
    would stay cached as-is even though a replace committed in between
    (same staleness ``cancel_submission``'s docstring documents). If the
    submitter's ``user_id`` no longer matches what authorization saw, this
    request's payload belongs to a signer who isn't this row's owner
    anymore — 409 rather than completing (or worse, silently misattributing
    values) on their behalf.
    """
    submitter = _get_submitter_authorized(db, submitter_id, identity)
    authorized_user_id = submitter.user_id
    submission_id = submitter.submission_id
    storage = get_storage(settings)

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()
    submitter = db.execute(
        select(Submitter).where(Submitter.id == submitter_id).execution_options(populate_existing=True),
    ).scalar_one()

    if submitter.user_id != authorized_user_id:
        db.rollback()
        raise HTTPException(status_code=409, detail="This signer was replaced; please use your new link")

    if submitter.status == "completed":
        outcome = _maybe_finalize(db, submission.id, storage)
        db.commit()
        if outcome == completion.FinalizeOutcome.FINALIZED and submission.status == "completed":
            notifications.on_submission_completed(db, submission, storage, settings)
            sharepoint.archive_submission(db, submission, storage, settings)
        return {"already": True}

    if submission.status != "pending":
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}")

    if _expiry_passed(submission):
        db.rollback()
        raise HTTPException(status_code=409, detail="This envelope has expired and can no longer be signed")

    if not _is_my_turn(submitter):
        db.rollback()
        raise HTTPException(status_code=409, detail="It isn't your turn to sign yet — earlier signers must finish first")

    my_fields = _my_fields(submitter)
    validated = _validate_values(db, submitter, my_fields, payload.values)

    ip = client_ip(request)
    submitter.values = validated
    submitter.status = "completed"
    submitter.signed_at = datetime.now(UTC)
    submitter.ip_address = ip
    audit.record(db, submission.id, "signed", actor_user_id=submitter.user_id, ip=ip, submitter_id=submitter.id)

    outcome = _maybe_finalize(db, submission.id, storage)

    db.commit()

    if outcome == completion.FinalizeOutcome.FINALIZED and submission.status == "completed":
        notifications.on_submission_completed(db, submission, storage, settings)
        sharepoint.archive_submission(db, submission, storage, settings)
    elif submission.status == "pending":
        # Ordered signing: this completion may have unlocked the next order
        # group — email any newly-active signers (post-commit, same "never
        # hold the transaction open on Graph" rule as creation emails).
        notifications.on_submitter_completed(db, submission, settings)
        db.commit()  # persists the email_status set just above

    return {"already": False}


@router.post("/{submitter_id}/decline")
def decline_signing(
    submitter_id: int,
    payload: SignDeclineIn,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    identity: SigningIdentity = Depends(signing_identity),
) -> dict:
    """Decline to sign, voiding the whole envelope.

    The status decision runs under a SELECT ... FOR UPDATE on the submission
    row with populate_existing — same pattern and race rationale as
    routers/submissions.py's cancel_submission (decline races the last
    co-signer's /complete the same way cancel does).
    """
    submitter = _get_submitter_authorized(db, submitter_id, identity)

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submitter.submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status != "pending" or submitter.status not in ("pending", "opened"):
        db.rollback()
        raise HTTPException(status_code=409, detail="Submission is not open for signing")

    if _expiry_passed(submission):
        db.rollback()
        raise HTTPException(status_code=409, detail="This envelope has expired and can no longer be signed")

    # Same rule as /complete: declining voids the whole envelope, so a
    # later-group signer can't kill it before earlier signers even hear
    # about it.
    if not _is_my_turn(submitter):
        db.rollback()
        raise HTTPException(status_code=409, detail="It is not your turn to sign yet")

    reason = payload.reason.strip() if payload.reason and payload.reason.strip() else None
    ip = client_ip(request)
    submitter.status = "declined"
    submitter.declined_at = datetime.now(UTC)
    submitter.decline_reason = reason
    submission.status = "declined"
    detail: dict = {"submitter_id": submitter.id}
    if reason:
        detail["reason"] = reason
    audit.record(db, submission.id, "declined", actor_user_id=submitter.user_id, ip=ip, **detail)
    db.commit()

    notifications.on_submission_declined(db, submission, submitter, settings)
    return {"ok": True}
