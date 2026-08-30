"""Submission routes: create (template-based and ad-hoc), list, view, correct
(title/message), cancel, remind.

Role-mapping validation (create): every role that appears on the target
template's fields must be mapped by exactly one entry in ``signers`` — no
role left unmapped, no extra roles, no role mapped twice — and every
``user_id`` given must be a real user. All of that is checked, and a
submission + its submitters are only ever written, inside a single
transaction that also writes the ``created``/``sent`` audit events; a
validation failure raises before anything is added to the session, so
nothing partial is ever flushed.

Ad-hoc submissions build a throwaway ``is_adhoc`` Template (named after the
submission title, with the given ``fields``) from an uploaded file using the
exact same conversion path as ``POST /api/templates``, then hand off to the
same submission-creation helper as the regular flow.
"""

import copy
import csv
import io
import secrets
from collections import Counter
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import TypeAdapter, ValidationError
from pypdf import PdfReader, PdfWriter
from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session, selectinload

from app import audit, completion, notifications, sharepoint
from app.auth import current_user, get_settings, require_admin, require_sender
from app.config import Settings
from app.conversion import ConversionError, to_pdf, to_pdf_bytes
from app.db import get_db
from app.http_utils import client_ip
from app.models import Attachment, AuditEvent, Submission, SubmissionArchive, Submitter, Template, User
from app.routers.templates import clone_template
from app.schemas import (
    AuditEventOut,
    FieldDef,
    FormDataEntryOut,
    FormDataOut,
    SignerIn,
    SubmissionCancelIn,
    SubmissionCreate,
    SubmissionOut,
    SubmissionPatch,
    SubmitterReplace,
    TemplateOut,
    UserBrief,
    validate_future_expiry,
)
from app.storage import get_storage

router = APIRouter(prefix="/api/submissions", tags=["submissions"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024
# Per the send-flow spec: CC lists are bounded (every CC row is an outbound
# email on several lifecycle events).
MAX_CC_RECIPIENTS = 10


async def _read_upload_within_limit(file: UploadFile) -> bytes:
    """Read ``file`` in chunks, raising 413 as soon as MAX_UPLOAD_BYTES is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds the 25 MB upload limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _submission_query() -> Select:
    """Base SELECT for Submission with template + submitters + submitter.user eagerly loaded."""
    return select(Submission).options(
        selectinload(Submission.template),
        selectinload(Submission.creator),
        selectinload(Submission.submitters).selectinload(Submitter.user),
    )


def _submission_out(submission: Submission, *, viewer_id: int) -> SubmissionOut:
    out = SubmissionOut.model_validate(submission)
    my_submitter = next((s for s in submission.submitters if s.user_id == viewer_id), None)
    out.my_submitter_id = my_submitter.id if my_submitter else None
    # Envelopes completed before the certificate became its own artifact
    # (issue #15) have no separate certificate to offer for download.
    out.has_certificate = submission.certificate_pdf_key is not None
    return out


def _apply_archived_flags(db: Session, outs: list[SubmissionOut], viewer_id: int) -> list[SubmissionOut]:
    """Set ``archived_by_me`` on ``outs`` from the viewer's SubmissionArchive rows."""
    if not outs:
        return outs
    archived_ids = set(
        db.scalars(
            select(SubmissionArchive.submission_id).where(
                SubmissionArchive.user_id == viewer_id,
                SubmissionArchive.submission_id.in_([o.id for o in outs]),
            ),
        ),
    )
    for out in outs:
        out.archived_by_me = out.id in archived_ids
    return outs


def _validate_role_mapping(template: Template, signers: list[SignerIn]) -> None:
    """Raise 422 unless ``signers`` maps every template role exactly once, with no extras.

    Template roles are the union of the persisted ``template.roles`` list and
    the roles referenced by fields — the union covers templates saved before
    ``roles`` existed (where the list is empty) without trusting either side
    alone. Every mapped role must also have at least one field: a signer
    whose role has nothing to fill could never meaningfully sign, so that's
    a template-building mistake surfaced here rather than a signing dead end.
    """
    # Label fields are role-less sender text — never mapped to a signer.
    field_roles = {field["role"] for field in template.fields if field.get("type") != "label"}
    template_roles = set(template.roles or []) | field_roles
    # CC rows carry no role — only actual signers participate in the mapping.
    signer_roles = [signer.role for signer in signers if not signer.is_cc]
    if not signer_roles:
        raise HTTPException(status_code=422, detail="at least one signer (non-CC recipient) is required")

    # One row per person: a duplicated user would get duplicate emails and
    # ambiguous "my submitter" resolution everywhere downstream.
    user_counts = Counter(signer.user_id for signer in signers)
    duplicate_users = sorted(str(uid) for uid, count in user_counts.items() if count > 1)
    if duplicate_users:
        raise HTTPException(
            status_code=422,
            detail=f"recipient(s) listed more than once (user id(s): {', '.join(duplicate_users)})",
        )

    cc_count = sum(1 for signer in signers if signer.is_cc)
    if cc_count > MAX_CC_RECIPIENTS:
        raise HTTPException(status_code=422, detail=f"at most {MAX_CC_RECIPIENTS} CC recipients are allowed")

    role_counts = Counter(signer_roles)
    duplicates = sorted(role for role, count in role_counts.items() if count > 1)
    if duplicates:
        raise HTTPException(status_code=422, detail=f"role(s) mapped more than once: {', '.join(duplicates)}")

    signer_role_set = set(signer_roles)
    missing = template_roles - signer_role_set
    if missing:
        raise HTTPException(status_code=422, detail=f"missing signer for role(s): {', '.join(sorted(missing))}")

    extra = signer_role_set - template_roles
    if extra:
        raise HTTPException(status_code=422, detail=f"role(s) not on template: {', '.join(sorted(extra))}")

    fieldless = sorted(signer_role_set - field_roles)
    if fieldless:
        raise HTTPException(
            status_code=422,
            detail=(
                f"role(s) have no signable fields: {', '.join(fieldless)} — "
                "add at least one field for them in the template builder"
            ),
        )


def _require_correction_rights(submission: Submission, user: User) -> None:
    """403 unless the caller may *correct* this envelope: its sender (still
    holding ``can_send``) or an admin.

    Correction-type actions — edit, document/signer replacement, remind,
    resend — send email and alter envelope content, so a sender whose send
    rights were revoked (e.g. offboarding) loses them too. Void and
    retry-completion deliberately stay plain sender-or-admin: harm-reduction
    must not be blockable by a role revocation.
    """
    is_sender = submission.created_by == user.id and user.can_send
    if not (is_sender or user.is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")


def _validate_users_exist(db: Session, signers: list[SignerIn]) -> None:
    """Raise 422 if any ``signers[].user_id`` doesn't reference a real user."""
    user_ids = [signer.user_id for signer in signers]
    existing = set(db.scalars(select(User.id).where(User.id.in_(user_ids))))
    unknown = sorted({uid for uid in user_ids if uid not in existing})
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown user id(s): {', '.join(str(u) for u in unknown)}")


def _create_submission(
    db: Session,
    *,
    template: Template,
    title: str,
    message: str | None,
    signers: list[SignerIn],
    actor: User,
    request: Request,
    expires_at: datetime | None = None,
    reminders_enabled: bool = True,
    reminder_interval_days: int = 3,
    draft: bool = False,
    created_detail: dict[str, object] | None = None,
) -> Submission:
    """Validate, then create a Submission + Submitters + `created`/`sent` audit events.

    ``draft=True`` creates the envelope in "draft" status: the ``sent``
    audit events are deferred to ``POST /{id}/send`` (nothing has been
    sent), and the caller must also skip its notification hook.

    Does not commit — the caller owns the transaction (so an ad-hoc creation
    can commit the new Template row atomically alongside the submission) —
    and does not send the "please sign" emails either: the caller does that
    itself, after its own ``db.commit()``, so a slow/hung Graph send can
    never block or fail the create transaction (see ``notifications.on_submission_created``'s
    docstring).
    """
    _validate_role_mapping(template, signers)
    _validate_users_exist(db, signers)
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_([s.user_id for s in signers])))}

    submission = Submission(
        template_id=template.id,
        title=title,
        message=message,
        status="draft" if draft else "pending",
        created_by=actor.id,
        expires_at=expires_at,
        reminders_enabled=reminders_enabled,
        reminder_interval_days=reminder_interval_days,
    )
    db.add(submission)
    db.flush()

    ip = client_ip(request)
    audit.record(db, submission.id, "created", actor_user_id=actor.id, ip=ip, detail=created_detail)

    for signer in signers:
        signer_user = users_by_id[signer.user_id]
        submitter = Submitter(
            submission_id=submission.id,
            user_id=signer.user_id,
            role=signer.role,
            order_index=signer.order,
            is_cc=signer.is_cc,
            status="pending",
            # External signers get a random link secret; internal signers keep
            # the plain /sign/{id} + login flow. CC rows never sign, so they
            # get no link either way.
            access_uid=secrets.token_hex(16) if signer_user.is_external and not signer.is_cc else None,
        )
        db.add(submitter)
        db.flush()
        if not draft:
            audit.record(db, submission.id, "sent", actor_user_id=actor.id, ip=ip, submitter_id=submitter.id)

    return submission


@router.post("", response_model=SubmissionOut, status_code=201)
def create_submission(
    payload: SubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> SubmissionOut:
    """Create a submission from an existing (non-archived) template the sender owns."""
    template = db.get(Template, payload.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.created_by != sender.id and not sender.is_admin and not template.shared:
        # Templates are private per user unless their owner shared them.
        raise HTTPException(status_code=403, detail="Forbidden")
    if template.archived_at is not None:
        raise HTTPException(status_code=409, detail="Template is archived")

    submission = _create_submission(
        db,
        template=template,
        title=payload.title,
        message=payload.message,
        signers=payload.signers,
        actor=sender,
        request=request,
        expires_at=payload.expires_at,
        reminders_enabled=payload.reminders_enabled,
        reminder_interval_days=payload.reminder_interval_days,
        draft=payload.draft,
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission.id)).one()
    if not payload.draft:
        notifications.on_submission_created(db, submission, settings)
        db.commit()  # small second commit: persists the email_status set just above

    return _submission_out(submission, viewer_id=sender.id)


@router.post("/adhoc/merged-document")
async def build_adhoc_merged_document(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> Response:
    """Convert each uploaded file to PDF and concatenate them, in upload order.

    Powers the send wizard's multi-file one-off envelopes (issue #1): the
    wizard needs the final merged document *before* sending, so fields can
    be placed on the real page layout; the merged PDF this returns is what
    the wizard then previews and eventually submits to ``POST /adhoc``.
    Office formats go through the same LibreOffice conversion as template
    uploads — in a worker thread, since a conversion can take up to two
    minutes and must not stall the event loop. Nothing is persisted.
    """
    converted: list[bytes] = []
    for upload in files:
        data = await _read_upload_within_limit(upload)
        filename = upload.filename or "upload"
        try:
            pdf_bytes, _page_count = await run_in_threadpool(to_pdf_bytes, data, filename, settings)
        except ConversionError as exc:
            raise HTTPException(status_code=422, detail=f"{filename}: {exc.reason}") from exc
        converted.append(pdf_bytes)

    def merge(parts: list[bytes]) -> bytes:
        writer = PdfWriter()
        for part in parts:
            for page in PdfReader(io.BytesIO(part)).pages:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    merged = await run_in_threadpool(merge, converted)
    return Response(content=merged, media_type="application/pdf")


@router.post("/adhoc", response_model=SubmissionOut, status_code=201)
async def create_adhoc_submission(
    request: Request,
    title: str = Form(...),
    signers_json: str = Form(...),
    fields_json: str = Form(...),
    file: UploadFile = File(...),
    message: str | None = Form(None),
    expires_at: str | None = Form(None),
    reminders_enabled: bool = Form(True),
    reminder_interval_days: int = Form(3, ge=1, le=30),
    draft: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> SubmissionOut:
    """Create a one-off (``is_adhoc``) template from an uploaded file, then a submission for it.

    Form fields: ``title`` (str), ``signers_json`` (JSON string, list of
    ``{"role": str, "user_id": int}``), ``fields_json`` (JSON string, list of
    ``FieldDef`` — the same shape used by ``PUT /api/templates/{id}/fields``),
    an optional ``message`` (str), and the ``file`` upload itself.
    """
    try:
        signers = TypeAdapter(list[SignerIn]).validate_json(signers_json)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"invalid signers_json: {exc}") from exc

    try:
        fields = TypeAdapter(list[FieldDef]).validate_json(fields_json)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"invalid fields_json: {exc}") from exc

    expires_at_dt: datetime | None = None
    if expires_at:
        # Form field, so pydantic isn't parsing/validating it — same rule as
        # SubmissionCreate.expires_at, applied by hand.
        try:
            expires_at_dt = validate_future_expiry(datetime.fromisoformat(expires_at))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"invalid expires_at: {exc}") from exc

    data = await _read_upload_within_limit(file)

    template = Template(
        name=title,
        created_by=sender.id,
        original_file_key="",
        pdf_key="",
        page_count=0,
        fields=[],
        is_adhoc=True,
    )
    db.add(template)
    db.flush()  # assign template.id without committing yet

    storage = get_storage(settings)
    key_prefix = f"templates/{template.id}"
    filename = file.filename or "upload"

    try:
        tmp_pdf_key, page_count = to_pdf(data, filename, storage, key_prefix, settings)
    except ConversionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    if any(field.page >= page_count for field in fields):
        storage.delete(tmp_pdf_key)
        db.rollback()
        raise HTTPException(status_code=422, detail="page out of range")

    pdf_bytes = storage.open(tmp_pdf_key)
    storage.delete(tmp_pdf_key)

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    original_key = f"{key_prefix}/original.{ext}" if ext else f"{key_prefix}/original"
    pdf_key = f"{key_prefix}/document.pdf"
    storage.save(original_key, data)
    storage.save(pdf_key, pdf_bytes)

    template.original_file_key = original_key
    template.pdf_key = pdf_key
    template.page_count = page_count
    template.fields = [field.model_dump() for field in fields]
    template.roles = list(dict.fromkeys(signer.role for signer in signers if not signer.is_cc))

    submission = _create_submission(
        db,
        template=template,
        title=title,
        message=message,
        signers=signers,
        actor=sender,
        request=request,
        expires_at=expires_at_dt,
        reminders_enabled=reminders_enabled,
        reminder_interval_days=reminder_interval_days,
        draft=draft,
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission.id)).one()
    if not draft:
        notifications.on_submission_created(db, submission, settings)
        db.commit()  # small second commit: persists the email_status set just above

    return _submission_out(submission, viewer_id=sender.id)


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    mine: Literal["sign", "sent"] = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[SubmissionOut]:
    """List submissions for the current user: ``mine=sign`` (any role) or ``mine=sent`` (whatever they created).

    Both branches are scoped to the caller's own id (``Submitter.user_id`` /
    ``Submission.created_by``), so no extra role gate is needed on
    ``mine=sent`` — any logged-in user, sender or not, can call it and just
    gets their own (possibly empty) list back. DashboardView relies on this:
    it fetches ``mine=sent`` for every ``can_send`` user, not only admins.
    """
    if mine == "sign":
        # Every envelope the caller is a party to, CC rows included (the
        # envelope-browser spec defines Inbox as "I'm a signer or CC"; the
        # frontend labels CC rows and never counts them as action-needed).
        # Voided envelopes stay listed too — recipients deserve to see that
        # an envelope was voided, not have it silently vanish.
        stmt = (
            _submission_query()
            .join(Submitter, Submitter.submission_id == Submission.id)
            # Drafts were never sent — their future recipients must not see
            # them (the signing routes 404 for them too).
            .where(Submitter.user_id == user.id, Submission.status != "draft")
            .order_by(Submission.created_at.desc())
        )
        submissions = list(db.scalars(stmt).unique())
        return _apply_archived_flags(db, [_submission_out(s, viewer_id=user.id) for s in submissions], user.id)

    # mine == "sent"
    stmt = _submission_query().where(Submission.created_by == user.id).order_by(Submission.created_at.desc())
    submissions = list(db.scalars(stmt).unique())
    return _apply_archived_flags(db, [_submission_out(s, viewer_id=user.id) for s in submissions], user.id)


def _get_submission_authorized(
    db: Session,
    submission_id: int,
    user: User,
    *,
    allow_admin: bool = False,
) -> Submission:
    """Load a submission (with submitters eager) for a party to it — its sender or a submitter.

    ``allow_admin=True`` additionally admits any admin (used by the events
    timeline). 404 when the submission doesn't exist, 403 otherwise.
    """
    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    if allow_admin and user.is_admin:
        return submission
    is_sender = submission.created_by == user.id
    is_submitter = any(s.user_id == user.id for s in submission.submitters)
    # Drafts are invisible to their would-be recipients until sent — being
    # listed on an unsent draft grants nothing.
    if submission.status == "draft":
        is_submitter = False
    if not (is_sender or is_submitter):
        raise HTTPException(status_code=403, detail="Forbidden")
    return submission


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Fetch a single submission, visible to its sender or any of its submitters."""
    submission = _get_submission_authorized(db, submission_id, user)
    return _apply_archived_flags(db, [_submission_out(submission, viewer_id=user.id)], user.id)[0]


@router.post("/{submission_id}/archive", response_model=SubmissionOut)
def archive_submission_for_me(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Hide this envelope from the caller's own lists (DocuSign-style delete-is-hide).

    Any party — sender or submitter — may archive; the envelope itself, its
    files, its audit trail, and every other participant's view are
    untouched. Idempotent.
    """
    submission = _get_submission_authorized(db, submission_id, user)
    existing = db.scalar(
        select(SubmissionArchive).where(
            SubmissionArchive.submission_id == submission_id,
            SubmissionArchive.user_id == user.id,
        ),
    )
    if existing is None:
        db.add(SubmissionArchive(submission_id=submission_id, user_id=user.id))
        db.commit()
    out = _submission_out(submission, viewer_id=user.id)
    out.archived_by_me = True
    return out


@router.post("/{submission_id}/unarchive", response_model=SubmissionOut)
def unarchive_submission_for_me(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Undo ``archive`` — the envelope reappears in the caller's lists. Idempotent."""
    submission = _get_submission_authorized(db, submission_id, user)
    existing = db.scalar(
        select(SubmissionArchive).where(
            SubmissionArchive.submission_id == submission_id,
            SubmissionArchive.user_id == user.id,
        ),
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return _submission_out(submission, viewer_id=user.id)


@router.post("/{submission_id}/replace-document", response_model=SubmissionOut)
async def replace_document(
    submission_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """DocuSign-style Correct: swap the underlying document, keeping every field.

    Allowed for the sender or an admin, on a pending envelope, and — the
    DocuSign rule — only while **no signer has signed yet** (their signature
    would otherwise sit on a document they never saw). Fields carry over
    unchanged (same normalized positions), so the new file must have at
    least as many pages as the highest field page.

    Template handling: an ad-hoc envelope owns its throwaway template, so
    the file is replaced in place. An envelope sent from a *shared*
    template gets a private clone (marked archived so it never appears in
    the Templates list) pointed at the new file — other envelopes and the
    template itself are untouched.

    The upload is converted (Graph/LibreOffice) *before* the row lock is
    taken — conversions can take minutes and must not hold a lock; the
    pending/nobody-signed decision is then made under ``SELECT ... FOR
    UPDATE`` exactly like ``correct_submission``.
    """
    precheck = db.get(Submission, submission_id)
    if precheck is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    _require_correction_rights(precheck, user)

    data = await _read_upload_within_limit(file)
    filename = file.filename or "upload"
    try:
        pdf_bytes, page_count = await run_in_threadpool(to_pdf_bytes, data, filename, settings)
    except ConversionError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status not in ("pending", "draft"):
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not correctable")

    signed_count = db.scalar(
        select(func.count())
        .select_from(Submitter)
        .where(
            Submitter.submission_id == submission_id,
            Submitter.is_cc.is_(False),
            Submitter.status == "completed",
        ),
    )
    if signed_count:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A signer has already signed this envelope — void it and send a new one instead.",
        )

    template = db.get(Template, submission.template_id)
    max_field_page = max((field["page"] for field in template.fields), default=-1)
    if max_field_page >= page_count:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=(
                f"The new document has {page_count} page(s), but fields are placed on "
                f"page {max_field_page + 1}. Upload a document with at least {max_field_page + 1} page(s)."
            ),
        )

    if template.is_adhoc:
        target = template
    else:
        target = Template(
            name=template.name,
            created_by=user.id,
            original_file_key="",
            pdf_key="",
            page_count=0,
            fields=copy.deepcopy(template.fields),
            roles=list(template.roles or []),
            # The clone exists solely to carry this one envelope's replaced
            # document — exactly what is_adhoc means. Marking it so makes a
            # *second* replace hit the in-place branch above instead of
            # cloning the clone and orphaning files on the volume.
            is_adhoc=True,
            # Hidden from the Templates list: this clone exists solely to
            # carry one envelope's replaced document.
            archived_at=datetime.now(UTC),
        )
        db.add(target)
        db.flush()
        submission.template_id = target.id

    storage = get_storage(settings)
    key_prefix = f"templates/{target.id}"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    original_key = f"{key_prefix}/original.{ext}" if ext else f"{key_prefix}/original"
    pdf_key = f"{key_prefix}/document.pdf"
    storage.save(original_key, data)
    storage.save(pdf_key, pdf_bytes)
    target.original_file_key = original_key
    target.pdf_key = pdf_key
    target.page_count = page_count

    audit.record(
        db,
        submission.id,
        "corrected",
        actor_user_id=user.id,
        ip=client_ip(request),
        detail={"changed": ["document"]},
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    # Post-commit, like every mail hook: contacted signers may have read (or
    # still have open) the old version — tell them it changed.
    notifications.on_document_replaced(db, submission, user, settings)
    return _submission_out(submission, viewer_id=user.id)


@router.patch("/{submission_id}", response_model=SubmissionOut)
def correct_submission(
    submission_id: int,
    payload: SubmissionPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Correct a pending submission's title/message/expiration/reminders; sender or admin.

    Mirrors ``cancel_submission``'s locking discipline: an unlocked
    creator-or-admin pre-check (cheap, and ``created_by`` never goes stale),
    then the actual "still pending?" decision made under a ``SELECT ... FOR
    UPDATE`` lock on the submission row, re-checked after acquiring it —
    otherwise an unlocked read-then-write here could race the last signer's
    ``/complete`` and silently edit a submission that just finished.

    ``SubmissionPatch`` guarantees at least one patchable field is present
    in the request body (``model_fields_set``), so only the fields actually
    given are considered — but "given" alone isn't "changed": a field is
    only applied, and only listed in the ``corrected`` audit event's
    ``changed`` detail, if its new value actually differs from what was
    already stored. A PATCH that changes nothing (every given field equal
    to its current value) writes no audit event and returns the submission
    as-is, still inside the same lock/commit so it doesn't leave the row
    locked.

    Changing ``expires_at`` also clears ``expiry_warned_at``: the "expiring
    soon" warning is send-once per deadline, and the old marker must not
    suppress the warning for the *new* deadline. No notification goes out
    for any of these setting changes (DocuSign's rule: corrections that
    touch no recipient info notify no one).
    """
    precheck = db.get(Submission, submission_id)
    if precheck is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    _require_correction_rights(precheck, user)

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status not in ("pending", "draft"):
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not correctable")

    provided = payload.model_fields_set
    changed: list[str] = []
    if "title" in provided and payload.title != submission.title:
        submission.title = payload.title
        changed.append("title")
    if "message" in provided and payload.message != submission.message:
        submission.message = payload.message
        changed.append("message")
    if "expires_at" in provided and payload.expires_at != submission.expires_at:
        submission.expires_at = payload.expires_at
        submission.expiry_warned_at = None
        changed.append("expires_at")
    if "reminders_enabled" in provided and payload.reminders_enabled != submission.reminders_enabled:
        submission.reminders_enabled = payload.reminders_enabled
        changed.append("reminders_enabled")
    if "reminder_interval_days" in provided and payload.reminder_interval_days != submission.reminder_interval_days:
        submission.reminder_interval_days = payload.reminder_interval_days
        changed.append("reminder_interval_days")

    if not changed:
        db.commit()  # release the row lock; nothing actually changed, so no audit event
        submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
        return _submission_out(submission, viewer_id=user.id)

    audit.record(
        db,
        submission.id,
        "corrected",
        actor_user_id=user.id,
        ip=client_ip(request),
        detail={"changed": changed},
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    return _submission_out(submission, viewer_id=user.id)


@router.put("/{submission_id}/submitters/{submitter_id}", response_model=SubmissionOut)
def replace_submitter(
    submission_id: int,
    submitter_id: int,
    payload: SubmitterReplace,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Replace a pending signer with a different user; allowed for its sender or any admin.

    Mirrors ``correct_submission``'s locking discipline: an unlocked
    creator-or-admin pre-check, then the "still pending?" decision made
    under a ``SELECT ... FOR UPDATE`` lock on the submission row, re-checked
    after acquiring it — same race this guards against (a replace landing
    after the last other signer's ``/complete`` must not silently edit a
    submission that just finished).

    Once past the lock: the target submitter must exist on this submission
    and not already be ``completed`` (409 — nothing to correct once signed),
    the new user must exist (404) and not already be a submitter on this
    envelope (409, would create two rows for one person). On success the
    submitter row is reset to a fresh "just sent" state (status, values,
    signed/declined bookkeeping, reminder counters) under the new user's
    identity. ``access_uid`` is regenerated (the same random-token generator
    used at submission creation) if the new user is external, else cleared —
    either way the *old* value stops matching any row, so the old signing
    link 404s immediately. The verification-code fields are cleared too:
    a leftover code hash from the old signer must not carry over.

    A fresh "please sign" email is sent to the new signer (via
    ``notifications.send_sign_request``, the same per-submitter helper
    ``on_submission_created`` uses) after this request's own commit — same
    reasoning as submission creation: a slow/hung Graph send must not hold
    the row lock or the correcting transaction open.
    """
    precheck = db.get(Submission, submission_id)
    if precheck is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    _require_correction_rights(precheck, user)

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status not in ("pending", "draft"):
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not correctable")

    submitter = db.scalars(
        select(Submitter).where(Submitter.id == submitter_id, Submitter.submission_id == submission_id),
    ).one_or_none()
    if submitter is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Submitter not found")

    if submitter.status == "completed":
        db.rollback()
        raise HTTPException(status_code=409, detail="Signer already signed")

    new_user = db.get(User, payload.user_id)
    if new_user is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="User not found")

    duplicate = db.scalar(
        select(func.count())
        .select_from(Submitter)
        .where(
            Submitter.submission_id == submission_id,
            Submitter.user_id == payload.user_id,
            Submitter.id != submitter_id,
        ),
    )
    if duplicate:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a submitter on this envelope")

    old_user = db.get(User, submitter.user_id)
    old_was_contacted = submitter.email_status is not None
    from_detail = {"user_id": submitter.user_id, "email": old_user.email if old_user else None}
    to_detail = {"user_id": new_user.id, "email": new_user.email}

    submitter.user_id = new_user.id
    submitter.status = "pending"
    submitter.values = {}
    submitter.signed_at = None
    submitter.ip_address = None
    submitter.last_reminded_at = None
    submitter.reminder_count = 0
    submitter.email_status = None
    submitter.declined_at = None
    submitter.decline_reason = None
    submitter.verification_code_hash = None
    submitter.verification_code_expires_at = None
    submitter.verification_attempts = 0
    # Same generator _create_submission uses: external signers get a random
    # link secret, internal signers keep the plain /sign/{id} + login flow.
    # The old access_uid (whatever it was) is overwritten either way, so it
    # stops matching any row and its emailed link 404s immediately.
    submitter.access_uid = secrets.token_hex(16) if new_user.is_external else None

    audit.record(
        db,
        submission.id,
        "corrected",
        actor_user_id=user.id,
        ip=client_ip(request),
        detail={"submitter_id": submitter.id, "from": from_detail, "to": to_detail},
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    replaced = next(s for s in submission.submitters if s.id == submitter_id)
    # Ordered routing: only email the replacement if their group is already
    # due (sign request for signers, copy notice for CC rows); otherwise
    # email_status stays NULL and the unlock hook
    # (notifications.on_submitter_completed) emails them when it is. Drafts
    # email nobody — POST /{id}/send does the first contact.
    if submission.status == "pending" and notifications.recipient_due(submission, replaced):
        notifications.send_recipient_email(db, replaced, submission, settings)
    # The swapped-out signer's link is dead the moment this commits — if they
    # were ever contacted, tell them, or the 404 looks broken (or phishy).
    if old_was_contacted and old_user is not None:
        notifications.on_submitter_removed(db, submission, old_user, settings)
    db.commit()  # small second commit: persists the email_status set just above

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    return _submission_out(submission, viewer_id=user.id)


@router.get("/{submission_id}/events", response_model=list[AuditEventOut])
def list_submission_events(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[AuditEventOut]:
    """The audit timeline for a submission — any party to it (or an admin).

    DocuSign-style (issue #15): the sender *and* every submitter can see the
    envelope's history; unrelated users can't. Signer IPs are still never
    part of the payload (see ``AuditEventOut``).
    """
    _get_submission_authorized(db, submission_id, user, allow_admin=True)

    stmt = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor))
        .where(AuditEvent.submission_id == submission_id)
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    )
    return [AuditEventOut.model_validate(event) for event in db.scalars(stmt)]


# Signature/initials are not data fields (DocuSign's rule — the signed PDF is
# their record); labels are sender text, not recipient input.
_FORM_DATA_EXCLUDED_FIELD_TYPES = ("signature", "initials", "label")


def _form_data_entries(db: Session, submission: Submission) -> list[FormDataEntryOut]:
    """One entry per (signer, data field), in routing order.

    ``value`` stays ``None`` until the owning signer completes; ``name``
    fields resolve to the signer's display name (they're stamped
    server-side, never stored in ``values``), ``attachment`` fields to the
    uploaded file's name.
    """
    template = submission.template
    signers = [s for s in sorted(submission.submitters, key=lambda s: (s.order_index, s.id)) if not s.is_cc]

    fields_by_role: dict[str, list[dict]] = {}
    for field in template.fields:
        if field.get("type") not in _FORM_DATA_EXCLUDED_FIELD_TYPES:
            fields_by_role.setdefault(field["role"], []).append(field)

    attachment_names = {
        row.id: row.filename
        for row in db.scalars(select(Attachment).where(Attachment.submitter_id.in_([s.id for s in signers])))
    }

    entries: list[FormDataEntryOut] = []
    for signer in signers:
        for field in fields_by_role.get(signer.role, []):
            value = None
            if signer.status == "completed":
                if field["type"] == "name":
                    value = signer.user.name
                else:
                    raw = signer.values.get(field["id"])
                    if field["type"] == "attachment":
                        value = attachment_names.get(raw) if isinstance(raw, int) else None
                    else:
                        value = raw
            entries.append(
                FormDataEntryOut(
                    submitter_id=signer.id,
                    recipient=UserBrief.model_validate(signer.user),
                    role="" if template.is_adhoc else signer.role,
                    field_id=field["id"],
                    field_type=field["type"],
                    page=field["page"],
                    value=value,
                    signed_at=signer.signed_at,
                ),
            )
    return entries


def _form_data_csv(submission: Submission, entries: list[FormDataEntryOut]) -> str:
    """DocuSign-style CSV: one row per field, values as entered (bools as true/false)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "envelope_id",
            "title",
            "recipient_name",
            "recipient_email",
            "role",
            "field_id",
            "field_type",
            "page",
            "value",
            "signed_at",
        ],
    )
    for entry in entries:
        if entry.value is True:
            value = "true"
        elif entry.value is False:
            value = "false"
        elif entry.value is None:
            value = ""
        else:
            value = str(entry.value)
        writer.writerow(
            [
                submission.public_uid,
                submission.title,
                entry.recipient.name,
                entry.recipient.email,
                entry.role,
                entry.field_id,
                entry.field_type,
                entry.page + 1,  # human page numbers
                value,
                entry.signed_at.isoformat() if entry.signed_at else "",
            ],
        )
    return buffer.getvalue()


@router.get("/{submission_id}/form-data", response_model=FormDataOut)
def get_form_data(
    submission_id: int,
    format_: Literal["json", "csv"] = Query("json", alias="format"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Response | FormDataOut:
    """DocuSign-style Form Data: every data field's entered value, per recipient.

    Sender-or-admin only — form data can contain *other* signers' entries,
    so recipients don't get it (they see their own input on the document).
    Drafts 409 (nothing has been collected). ``?format=csv`` downloads the
    same entries as a CSV.
    """
    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.created_by != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    if submission.status == "draft":
        raise HTTPException(status_code=409, detail="Drafts have no form data yet")

    entries = _form_data_entries(db, submission)
    if format_ == "csv":
        csv_text = _form_data_csv(submission, entries)
        filename = f"{submission.title} - form data.csv"
        ascii_fallback = filename.encode("ascii", "ignore").decode().strip() or "form-data.csv"
        disposition = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": disposition},
        )

    return FormDataOut(
        submission_id=submission.id,
        public_uid=submission.public_uid,
        title=submission.title,
        status=submission.status,
        entries=entries,
    )


@router.post("/{submission_id}/cancel", response_model=SubmissionOut)
def cancel_submission(
    submission_id: int,
    request: Request,
    payload: SubmissionCancelIn | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Cancel a pending submission; allowed for its sender or any admin.

    An optional ``reason`` in the body is recorded in the audit trail and
    included in the void notification, which goes (post-commit, like every
    other mail hook) to everyone who had already been contacted about the
    envelope — a voided envelope must never just silently disappear on the
    people holding sign links or waiting for a copy.

    The 404/403 pre-checks below are unlocked (no need to block on a row
    lock just to check who's asking; ``created_by`` is immutable so it can
    never itself be stale), but the actual "is it still pending?" decision
    is made under a ``SELECT ... FOR UPDATE`` lock on the submission row —
    mirroring ``completion.finalize_if_ready`` — and re-checked *after*
    acquiring it. Without that, an unlocked read-then-write here races the
    last signer's ``/complete``: both requests can read ``status ==
    "pending"`` before either commits, and if cancel's write lands after
    the signer's completion commits, the submission ends up ``"cancelled"``
    despite already having a signed PDF, a ``"completed"`` audit event, and
    now a contradictory ``"cancelled"`` one appended after it. Taking the
    lock first forces the two requests to serialize: whichever commits
    first wins, and the loser's post-lock status re-read (no longer
    ``"pending"`` either way) correctly 409s instead of silently
    clobbering the other's outcome.

    ``execution_options(populate_existing=True)`` on the locked select is
    load-bearing, not decorative: the unlocked ``precheck`` above already
    loaded this same ``Submission`` into the session's identity map, and by
    default SQLAlchemy returns that *same* cached Python object as-is from
    a later query rather than overwriting its attributes with the row the
    ``FOR UPDATE`` just read — so without ``populate_existing``, the status
    check below would silently read the pre-lock cached value (exactly the
    staleness this lock exists to prevent) instead of what the lock
    actually made current.
    """
    precheck = db.get(Submission, submission_id)
    if precheck is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_sender = precheck.created_by == user.id
    if not (is_sender or user.is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status != "pending":
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not pending")

    reason = None
    if payload is not None and payload.reason and payload.reason.strip():
        reason = payload.reason.strip()

    submission.status = "cancelled"
    detail = {"reason": reason} if reason else None
    audit.record(db, submission.id, "cancelled", actor_user_id=user.id, ip=client_ip(request), detail=detail)
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    notifications.on_submission_cancelled(db, submission, user, settings, reason)
    return _submission_out(submission, viewer_id=user.id)


# Field types whose signer-entered values a Copy carries forward as
# editable prefills (DocuSign behavior). Signature/initials are personal,
# date/name auto-fill at signing, attachments are files — none copy.
_COPYABLE_VALUE_TYPES = {"text", "dropdown", "radio", "checkbox"}
_PREFILL_MAX_LENGTH = 500  # FieldDef.default_value's limit


def _fields_with_copied_values(fields: list[dict], values_by_role: dict[str, dict]) -> list[dict]:
    """Return a copy of ``fields`` with signer-entered values as ``default_value`` prefills.

    A field the submitter has *any* recorded value for (including a
    cleared/unchecked/invalid one) has its existing prefill dropped first —
    otherwise a stale ``default_value`` carried over from an earlier Copy
    (or set by the sender, then overwritten by signing) could resurrect a
    value the signer explicitly cleared. Fields with no recorded value at
    all keep whatever prefill they already had.
    """
    result = []
    for field in fields:
        field = dict(field)
        role_values = values_by_role.get(field.get("role", ""), {})
        if field.get("type") in _COPYABLE_VALUE_TYPES and field["id"] in role_values:
            field.pop("default_value", None)
            value = role_values[field["id"]]
            if field["type"] == "checkbox":
                if value is True:
                    field["default_value"] = "true"
            elif field["type"] in ("dropdown", "radio"):
                if isinstance(value, str) and value in (field.get("options") or []):
                    field["default_value"] = value
            elif isinstance(value, str) and value.strip():
                field["default_value"] = value[:_PREFILL_MAX_LENGTH]
        result.append(field)
    return result


@router.post("/{submission_id}/copy", response_model=SubmissionOut, status_code=201)
def copy_submission(
    submission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> SubmissionOut:
    """DocuSign-style "Copy": a new draft with the source's document,
    recipients, message, and settings — none of its signing history.

    Sender-or-admin, any source status (re-sending a completed or voided
    envelope is the point). The copy's expiration is kept only while still
    in the future — a stale deadline would make the draft undispatchable.
    Every copy is standalone: the source's template is deep-cloned into a
    new ad-hoc template so deleting the copy can never destroy the source's
    files, and editing the copy (e.g. prefills) can't touch the original.
    """
    source = db.scalars(_submission_query().where(Submission.id == submission_id)).one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if source.created_by != sender.id and not sender.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Every copy is standalone (DocuSign behavior): a deep ad-hoc clone,
    # never a reference — so editing the copy can't touch a reusable
    # template, and value-prefills (below) have a private home.
    template = clone_template(
        db,
        settings,
        source.template,
        owner_id=sender.id,
        name=source.template.name,
        is_adhoc=True,
    )
    values_by_role = {s.role: s.values for s in source.submitters if not s.is_cc}
    template.fields = _fields_with_copied_values(template.fields, values_by_role)

    signers = [
        SignerIn(role=s.role, user_id=s.user_id, order=s.order_index, is_cc=s.is_cc)
        for s in sorted(source.submitters, key=lambda s: (s.order_index, s.id))
    ]
    expires_at = source.expires_at if source.expires_at and source.expires_at > datetime.now(UTC) else None

    submission = _create_submission(
        db,
        template=template,
        title=source.title,
        message=source.message,
        signers=signers,
        actor=sender,
        request=request,
        expires_at=expires_at,
        reminders_enabled=source.reminders_enabled,
        reminder_interval_days=source.reminder_interval_days,
        draft=True,
        created_detail={"copied_from_submission_id": source.id},
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission.id)).one()
    return _submission_out(submission, viewer_id=sender.id)


@router.post("/{submission_id}/save-as-template", response_model=TemplateOut, status_code=201)
def save_as_template(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    sender: User = Depends(require_sender),
) -> Template:
    """DocuSign "Save as Template": turn an envelope into a reusable template.

    Sender-or-admin, any source status — the point is capturing an envelope
    that already worked (fields placed, roles settled) for repeat sends.
    The new template is a private, unshared copy named after the envelope,
    with its own storage files (``clone_template``'s rule: files follow
    their row's lifecycle, never shared between rows).

    An ad-hoc source's ``signer-N`` role strings are internal bookkeeping
    ids, never meant to be user-facing — they're generalized to "Signer 1",
    "Signer 2", ... in routing order (DocuSign's exact transformation of
    concrete recipients into role recipients).
    """
    source = db.scalars(_submission_query().where(Submission.id == submission_id)).one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if source.created_by != sender.id and not sender.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    template = source.template
    clone = clone_template(
        db,
        settings,
        template,
        owner_id=sender.id,
        name=source.title,
        is_adhoc=False,
    )
    if template.is_adhoc:
        # New dicts, not in-place edits: clone_template's field list still
        # shares its dict objects with the source template's JSONB value.
        mapping = {role: f"Signer {i + 1}" for i, role in enumerate(template.roles or [])}
        clone.roles = [mapping.get(role, role) for role in (template.roles or [])]
        clone.fields = [
            {**field, "role": mapping.get(field["role"], field["role"])} if field.get("type") != "label" else dict(field)
            for field in clone.fields
        ]
    db.commit()
    db.refresh(clone)
    return clone


@router.post("/{submission_id}/send", response_model=SubmissionOut)
def send_draft(
    submission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Dispatch a draft: flip it to pending, write the deferred ``sent`` audit
    events, and email every recipient whose routing group is due.

    Allowed for the sender (still holding ``can_send``) or an admin — the
    same rights as every correction-type action, since sending is the whole
    point of a draft. Runs under the usual row lock so a concurrent send or
    delete can't double-dispatch; a draft whose expiry date already passed
    is rejected (it would be born expired).
    """
    precheck = db.get(Submission, submission_id)
    if precheck is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    _require_correction_rights(precheck, user)

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status != "draft":
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not a draft")

    if submission.expires_at is not None and submission.expires_at <= datetime.now(UTC):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This draft's expiration date has already passed — update it before sending",
        )

    submitters = db.scalars(
        select(Submitter).where(Submitter.submission_id == submission_id).order_by(Submitter.id),
    ).all()
    # Re-validate against the template's *current* fields: they may have
    # changed since the draft was saved, and dispatching an envelope whose
    # signers have nothing to sign is the exact condition create rejects.
    template = db.get(Template, submission.template_id)
    signer_inputs = [SignerIn(role=s.role, user_id=s.user_id, order=s.order_index, is_cc=s.is_cc) for s in submitters]
    try:
        _validate_role_mapping(template, signer_inputs)
    except HTTPException:
        db.rollback()
        raise

    submission.status = "pending"
    ip = client_ip(request)
    for submitter in submitters:
        audit.record(db, submission.id, "sent", actor_user_id=user.id, ip=ip, submitter_id=submitter.id)
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    notifications.on_submission_created(db, submission, settings)
    db.commit()  # small second commit: persists the email_status set just above

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    return _submission_out(submission, viewer_id=user.id)


@router.delete("/{submission_id}", status_code=204)
def delete_draft(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> Response:
    """Delete a draft outright; sender or admin.

    Only drafts: nothing was ever sent, so there's no history worth keeping
    — the audit trail goes with it. Anything past draft must be voided
    instead (the trail is the record). An ad-hoc draft owns its throwaway
    template, so that row and its files are removed too.

    Deliberately looser than send/correct (which require the sender to still
    hold ``can_send``): a revoked sender may still clean up their own unsent
    drafts — deletion sends nothing and alters no record anyone else has.
    """
    precheck = db.get(Submission, submission_id)
    if precheck is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_sender = precheck.created_by == user.id
    if not (is_sender or user.is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status != "draft":
        db.rollback()
        raise HTTPException(status_code=409, detail="Only drafts can be deleted — void the envelope instead")

    template = db.get(Template, submission.template_id)
    db.execute(delete(AuditEvent).where(AuditEvent.submission_id == submission_id))
    db.execute(delete(SubmissionArchive).where(SubmissionArchive.submission_id == submission_id))
    db.delete(submission)  # submitters cascade via the relationship
    db.flush()

    if template is not None and template.is_adhoc:
        storage = get_storage(settings)
        for key in (template.original_file_key, template.pdf_key):
            if key:
                storage.delete(key)
        db.delete(template)

    db.commit()
    return Response(status_code=204)


@router.post("/{submission_id}/retry-completion", response_model=SubmissionOut)
def retry_completion(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Re-run completion for a submission stuck at "pending" despite every submitter being done.

    This is the recovery path for the failure mode ``completion.finalize``
    is deliberately silent about: a stamping/storage error during the last
    signer's ``/complete`` call leaves the submission "pending" (on
    purpose, so that request still succeeds) with no signed PDF. Allowed
    for the submission's sender or any admin.

    The 409 checks below are a fast-path pre-check for the common cases
    (nice error message, no lock contention for the overwhelmingly common
    "not ready yet" case) — but they are *not* the authoritative check.
    The actual decision of whether to finalize happens inside
    ``completion.finalize_if_ready``, under a ``SELECT ... FOR UPDATE`` lock
    on the submission row, which is what prevents two concurrent retries
    (or a retry racing an in-flight last-signer ``/complete``) from both
    passing these pre-checks and both calling ``finalize`` — that would
    double-write the ``completed`` audit event and send a duplicate
    completion email. If the submission stops being ready
    between the pre-check and the lock (e.g. a concurrent caller wins the
    race first), ``finalize_if_ready`` reports that and this route responds
    409 rather than silently no-op-ing with a 200.

    On success, returns the submission's current state; on a *repeat*
    stamping failure (``finalize`` swallows its own exceptions), also
    returns 200 with the submission still "pending" — callers should check
    ``status`` to see whether this attempt actually succeeded.

    The completion email is sent *after* this route's own ``db.commit()``
    (never from inside ``finalize``/``finalize_if_ready``, which run under
    a row lock — see ``app.completion``'s module docstring), and only if
    the post-commit reload shows ``status == "completed"``.
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    is_sender = submission.created_by == user.id
    if not (is_sender or user.is_admin):
        raise HTTPException(status_code=403, detail="Forbidden")

    if submission.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not pending")

    still_open = db.scalar(
        select(func.count())
        .select_from(Submitter)
        .where(
            Submitter.submission_id == submission_id,
            Submitter.is_cc.is_(False),
            Submitter.status != "completed",
        ),
    )
    if still_open != 0:
        raise HTTPException(status_code=409, detail="Not all submitters have completed")

    storage = get_storage(settings)
    outcome = completion.finalize_if_ready(db, submission_id, storage)
    if outcome != completion.FinalizeOutcome.FINALIZED:
        db.rollback()
        raise HTTPException(status_code=409, detail="Submission is not ready to finalize")
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    if submission.status == "completed":
        notifications.on_submission_completed(db, submission, storage, settings)
        sharepoint.archive_submission(db, submission, storage, settings)
    return _submission_out(submission, viewer_id=user.id)


@router.post("/{submission_id}/remind")
def remind_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> dict[str, str]:
    """Manually trigger reminder emails for a pending submission; sender or admin.

    Delegates to ``notifications.send_reminders_for`` with ``min_days=0`` —
    a sender explicitly asking for a reminder bypasses the normal 3-day
    wait between reminders (but not the reminder cap or the pending/
    opened-only submitter status rule), which is also responsible for
    recording any ``reminded`` audit events and enforcing the per-submitter
    reminder cap.
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")

    _require_correction_rights(submission, user)

    if submission.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not pending")

    notifications.send_reminders_for(db, submission, settings, min_days=0)
    db.commit()
    return {"status": "ok"}


@router.post("/{submission_id}/submitters/{submitter_id}/resend", response_model=SubmissionOut)
def resend_invite(
    submission_id: int,
    submitter_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(current_user),
) -> SubmissionOut:
    """Re-send one recipient's invite (sign request or CC copy notice), resetting their reminder budget.

    The bounce-recovery path: when an address bounced (``email_status ==
    "failed"``) the sender fixes the contact info and clicks Resend — without
    this, a recipient whose ``reminder_count`` hit the cap could never be
    emailed a working link again (remind returns 200 while sending nothing).
    Deliberately allowed even when the previous send succeeded ("they can't
    find the email") — the reset only affects this one recipient.
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    _require_correction_rights(submission, user)
    if submission.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}, not pending")

    submitter = db.scalars(
        select(Submitter).where(Submitter.id == submitter_id, Submitter.submission_id == submission_id),
    ).one_or_none()
    if submitter is None:
        raise HTTPException(status_code=404, detail="Submitter not found")
    if submitter.status in ("completed", "declined"):
        raise HTTPException(status_code=409, detail="This recipient has already acted on the envelope")

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    if not notifications.recipient_due(submission, submitter):
        raise HTTPException(status_code=409, detail="It is not this signer's turn yet — nothing to resend")

    submitter.reminder_count = 0
    submitter.email_status = None
    notifications.send_recipient_email(db, submitter, submission, settings)
    audit.record(
        db,
        submission.id,
        "reminded",
        actor_user_id=user.id,
        detail={"resend": True, "submitter_id": submitter.id},
    )
    db.commit()

    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one()
    return _submission_out(submission, viewer_id=user.id)


@router.get("/{submission_id}/dev-signing-links")
def dev_signing_links(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _admin: User = Depends(require_admin),
) -> list[dict]:
    """Dev/e2e-only: each submitter's access_uid. 404s (like dev-login) unless
    DEV_AUTH_BYPASS — tests can't read the signer's mailbox for the link."""
    if not settings.dev_auth_bypass:
        raise HTTPException(status_code=404)
    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return [{"submitter_id": s.id, "access_uid": s.access_uid} for s in submission.submitters]
