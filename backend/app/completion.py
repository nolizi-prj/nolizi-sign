"""Submission completion trigger, called once the last submitter signs.

This module owns the "what happens when everyone has signed" transition:
stamp every completed submitter's values onto the template PDF (plus a
generated audit/certificate page), save the result to storage, flip
``Submission.status`` to ``completed``, and record the ``completed`` audit
event.

Deliberately does **not** send the completion email itself.
``notifications.on_submission_completed`` sends via Microsoft Graph, which
can hang for a couple of minutes on an outage/retry; if that ran here, it
would run *while* ``finalize_if_ready`` still holds a ``SELECT ... FOR
UPDATE`` lock on the submission row, so a slow Graph call would leave the
row locked for as long as the send takes. Instead, the caller (the last
signer's ``/complete``, or ``POST /api/submissions/{id}/retry-completion``)
sends the completion email itself, *after* its own ``db.commit()`` — once
the lock is released — and only when this call actually flipped the
submission to ``completed`` (check ``FinalizeOutcome.FINALIZED`` *and*
``submission.status == "completed"`` post-commit; ``FINALIZED`` alone
doesn't guarantee success — see ``finalize_if_ready``'s docstring).

Like ``audit.record``, ``finalize`` flushes but never commits — the caller
owns the transaction boundary. Per the Task 6 contract, ``finalize`` is
called mid-transaction, under a ``SELECT ... FOR UPDATE`` lock on the
submission row, before the caller's single ``db.commit()``.

``finalize_if_ready`` is the *only* code path that should decide whether to
call ``finalize`` — it takes that row lock itself, so every caller (the
last signer's ``/complete``, ``POST /api/submissions/{id}/retry-completion``,
and any future caller) serializes through the same guarded check instead of
each doing its own unlocked "is this submission ready?" read. See its
docstring for why an unlocked check-then-act is unsafe here.

**Failure handling**: stamping/storage is inherently more failure-prone
than a status flip (missing files, oversized images, a transient storage
error, a bug in the stamping code) — and per the controller decision, a
failure here must never fail the signer's ``/complete`` request, and must
never leave the submission in a half-updated state. So this function does
all storage reads/writes and PDF building *first*, inside a try/except,
strictly before touching any DB row; only once the signed PDF is
successfully built and saved does it apply the DB mutations (status,
completed_at, signed_pdf_key, audit event). If anything in the try block
raises, it's logged and swallowed, and the function returns with the
submission left exactly as it was (still "pending") — no partial state is
ever possible, and no exception ever propagates to the caller.
``POST /api/submissions/{id}/retry-completion`` (routers/submissions.py)
re-invokes this function to recover from that state once the underlying
problem is fixed.
"""

import logging
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.models import Attachment, AuditEvent, Signature, Submission, Submitter, Template, User
from app.stamping import append_attachments, build_certificate_pdf, build_signed_pdf
from app.storage import FileStorage

logger = logging.getLogger(__name__)


class FinalizeOutcome(StrEnum):
    """What ``finalize_if_ready`` did, for callers that need to react differently."""

    FINALIZED = "finalized"
    NOT_PENDING = "not_pending"
    NOT_ALL_COMPLETED = "not_all_completed"


def _signed_pdf_key(submission_id: int) -> str:
    return f"submissions/{submission_id}/signed.pdf"


def _certificate_pdf_key(submission_id: int) -> str:
    return f"submissions/{submission_id}/certificate.pdf"


def _field_ids_of_types(fields: list[dict], types: tuple[str, ...]) -> set[str]:
    return {field["id"] for field in fields if field.get("type") in types}


def _gather_signature_images(
    db: Session,
    storage: FileStorage,
    submitters: list[Submitter],
    fields: list[dict],
) -> dict[str, bytes]:
    """Collect PNG bytes for every signature id referenced across ``submitters``' values.

    Filtered by field type, not just value shape: attachment fields also
    store plain ``int`` ids (of ``Attachment`` rows), so "any int value"
    would happily look up an attachment id in the signatures table and, on
    a coincidental id match, stamp some unrelated user's signature image.
    """
    signature_field_ids = _field_ids_of_types(fields, ("signature", "initials"))
    signature_ids: set[int] = set()
    for submitter in submitters:
        for field_id, value in submitter.values.items():
            if field_id in signature_field_ids and isinstance(value, int) and not isinstance(value, bool):
                signature_ids.add(value)

    if not signature_ids:
        return {}

    signatures = db.scalars(select(Signature).where(Signature.id.in_(signature_ids))).all()
    return {str(sig.id): storage.open(sig.image_key) for sig in signatures}


def _gather_attachments(db: Session, submitters: list[Submitter], fields: list[dict]) -> list[Attachment]:
    """The ``Attachment`` rows referenced by ``submitters``' attachment-field
    values, in deterministic (submitter, field-definition) order — the order
    their pages are appended to the signed PDF."""
    attachment_field_ids = [field["id"] for field in fields if field.get("type") == "attachment"]
    if not attachment_field_ids:
        return []

    referenced: list[int] = []
    for submitter in submitters:
        for field_id in attachment_field_ids:
            value = submitter.values.get(field_id)
            if isinstance(value, int) and not isinstance(value, bool):
                referenced.append(value)

    if not referenced:
        return []

    rows_by_id = {row.id: row for row in db.scalars(select(Attachment).where(Attachment.id.in_(referenced)))}
    return [rows_by_id[attachment_id] for attachment_id in referenced if attachment_id in rows_by_id]


def _gather_audit_rows(db: Session, submission_id: int) -> list[dict]:
    """Return every audit event for ``submission_id``, oldest first, joined to actor identity."""
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission_id).order_by(AuditEvent.created_at),
    ).all()

    actor_ids = {e.actor_user_id for e in events if e.actor_user_id is not None}
    actors_by_id: dict[int, User] = {}
    if actor_ids:
        actors_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_(actor_ids))).all()}

    rows = []
    for event in events:
        actor = actors_by_id.get(event.actor_user_id) if event.actor_user_id is not None else None
        rows.append(
            {
                "event": event.event,
                "actor_name": actor.name if actor else None,
                "actor_email": actor.email if actor else None,
                "ip": event.ip_address,
                "created_at": event.created_at,
            },
        )
    return rows


def _build_and_save_signed_pdf(
    db: Session,
    storage: FileStorage,
    submission: Submission,
    completed_at: datetime,
) -> tuple[str, str] | None:
    """Build and save the signed PDF and the signature-certificate PDF.

    Returns ``(signed_key, certificate_key)``, or ``None`` on any failure.

    ``completed_at`` is stamped into the per-page watermark (see
    ``app.stamping``) and must be the exact same value the caller then
    writes to ``submission.completed_at`` on success, so the watermark and
    the DB row never disagree.

    Does not touch any DB row (no writes/flushes of ORM state) — only
    reads, plus storage writes. Any exception is logged and swallowed so
    the caller can decide what (not) to do to the submission.
    """
    try:
        template = db.get(Template, submission.template_id)
        if template is None:
            raise ValueError(f"Template {submission.template_id} not found")
        template_pdf = storage.open(template.pdf_key)

        submitters = list(
            db.scalars(
                select(Submitter).where(
                    Submitter.submission_id == submission.id,
                    # Signers only: CC rows never sign and must not appear on
                    # the certificate (their status stays "pending" anyway).
                    Submitter.is_cc.is_(False),
                    Submitter.status == "completed",
                ),
            ),
        )
        users_by_id = {
            u.id: u for u in db.scalars(select(User).where(User.id.in_({s.user_id for s in submitters}))).all()
        }
        signature_images = _gather_signature_images(db, storage, submitters, template.fields)
        attachments = _gather_attachments(db, submitters, template.fields)
        audit_rows = _gather_audit_rows(db, submission.id)

        pdf_bytes = build_signed_pdf(
            template_pdf,
            template.fields,
            submitters,
            users_by_id,
            signature_images,
            envelope_uid=submission.public_uid,
            completed_at=completed_at,
            attachment_names={str(a.id): a.filename for a in attachments},
        )
        pdf_bytes = append_attachments(
            pdf_bytes,
            [(a.filename, storage.open(a.file_key)) for a in attachments],
        )
        certificate_bytes = build_certificate_pdf(
            submitters,
            users_by_id,
            audit_rows,
            submission_title=submission.title,
            envelope_uid=submission.public_uid,
            template_name=template.name,
            is_adhoc=template.is_adhoc,
        )

        signed_key = _signed_pdf_key(submission.id)
        certificate_key = _certificate_pdf_key(submission.id)
        storage.save(signed_key, pdf_bytes)
        storage.save(certificate_key, certificate_bytes)
    except Exception:
        logger.exception("Failed to stamp/save signed PDF for submission %s", submission.id)
        return None
    else:
        return signed_key, certificate_key


# The watermark line for a non-completed rendition, by submission status.
# Terminal statuses get an honest label (DocuSign's VOID-watermark rule: a
# dead envelope's document must not read as live); anything else — draft,
# pending — is genuinely in progress. "cancelled" is displayed as "Voided"
# everywhere user-facing (see frontend labels), the watermark included.
_PREVIEW_STATUS_NOTES = {"cancelled": "Voided", "declined": "Declined", "expired": "Expired"}


def build_preview_pdf(db: Session, storage: FileStorage, submission: Submission) -> bytes:
    """Return the document as it currently stands, DocuSign-style.

    Completed envelope with a stored signed PDF → that PDF, verbatim.
    Otherwise: the template PDF with every *already-completed* submitter's
    field values stamped and a status watermark — "In progress" while the
    envelope is live, "Voided"/"Declined"/"Expired" once it's terminal —
    so signer N sees signers 1..N-1's signatures and a dead envelope's
    rendition can't pass as a live document. With nobody signed yet this
    still stamps labels (sender text baked into the document) — the
    closest thing to "the document as sent".

    Generated on demand, never cached or persisted — unlike ``finalize``,
    a failure here is the caller's (HTTP 500), not swallowed.
    """
    if submission.status == "completed" and submission.signed_pdf_key:
        return storage.open(submission.signed_pdf_key)

    template = db.get(Template, submission.template_id)
    if template is None:
        raise ValueError(f"Template {submission.template_id} not found")
    template_pdf = storage.open(template.pdf_key)

    submitters = list(
        db.scalars(
            select(Submitter).where(
                Submitter.submission_id == submission.id,
                Submitter.is_cc.is_(False),
                Submitter.status == "completed",
            ),
        ),
    )
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_({s.user_id for s in submitters}))).all()}
    signature_images = _gather_signature_images(db, storage, submitters, template.fields)
    # Names only — the boxes get their "[Attached: ...]" note, but the files
    # themselves are appended to the *final* PDF only, at completion.
    attachments = _gather_attachments(db, submitters, template.fields)

    return build_signed_pdf(
        template_pdf,
        template.fields,
        submitters,
        users_by_id,
        signature_images,
        envelope_uid=submission.public_uid,
        completed_at=None,
        status_note=_PREVIEW_STATUS_NOTES.get(submission.status),
        attachment_names={str(a.id): a.filename for a in attachments},
    )


def finalize(db: Session, submission_id: int, storage: FileStorage) -> None:
    """Stamp, save, and mark ``submission_id`` as fully completed.

    Builds the signed PDF from every completed submitter's values and
    saves it to storage *before* making any database change. On success:
    sets ``signed_pdf_key``, flips ``status`` to ``"completed"``, sets
    ``completed_at``, and records a ``completed`` audit event (no actor —
    this is a system transition). Does **not** send the completion email —
    see this module's docstring for why that's the caller's job, done after
    its own commit. On any stamping/storage failure: logs the exception and
    returns, leaving the submission untouched (still ``"pending"``) — the
    caller's request still succeeds; ``POST /api/submissions/{id}/retry-completion``
    re-runs this later.
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise ValueError(f"Submission {submission_id} not found")

    completed_at = datetime.now(UTC)
    keys = _build_and_save_signed_pdf(db, storage, submission, completed_at)
    if keys is None:
        return

    submission.signed_pdf_key, submission.certificate_pdf_key = keys
    submission.status = "completed"
    submission.completed_at = completed_at
    audit.record(db, submission_id, "completed", actor_user_id=None, ip=None)
    db.flush()


def finalize_if_ready(db: Session, submission_id: int, storage: FileStorage) -> FinalizeOutcome:
    """Finalize ``submission_id`` if — and only if — it's ready, under a row lock.

    This is the single authoritative "is this submission ready to
    finalize?" check, guarded by ``SELECT ... FOR UPDATE`` on the
    submission row. It exists because a plain check-then-act (read
    submitter statuses, decide, then call ``finalize``) is unsafe whenever
    more than one caller can reach it for the same submission: two
    concurrent callers — the last two signers completing at nearly the same
    moment, a sender/admin double-clicking retry, or a retry racing an
    in-flight last-signer ``/complete`` — could each read a snapshot before
    the other's transaction commits, each conclude independently that
    *they* should finalize, and either strand the submission at "pending"
    forever (if neither goes first, see the concurrent-completion race this
    was originally introduced for) or, worse, both actually call
    ``finalize`` and double-write the ``completed`` audit event. The lock
    also indirectly prevents a duplicate completion email: only the one
    caller whose ``finalize`` invocation actually flips the row to
    ``completed`` should send it (see this module's docstring) — every
    other caller either never reaches ``finalize`` at all, or reaches it
    only after the winner's commit, at which point the fresh re-read below
    already shows ``status != "pending"`` and returns ``NOT_PENDING``.

    Taking the lock first forces every caller to serialize: whichever loses
    the race blocks until the winner's transaction commits (releasing the
    lock), then re-reads ``submission.status``/submitter statuses fresh —
    now including whatever the winner just did — before deciding. At most
    one caller ever actually invokes ``finalize`` for a given "ready"
    window. ``db.flush()`` first makes this same request's own pending
    writes (e.g. the signer's own submitter-status change, not yet
    committed) visible to the queries below.

    Also self-heals: calling this on an already-completed or
    not-yet-fully-signed submission is always a safe no-op (returns
    ``NOT_PENDING``/``NOT_ALL_COMPLETED`` without touching anything), so
    callers can call it liberally — including from an idempotent
    already-completed branch — to notice and recover a submission that
    somehow ended up stranded despite every submitter being done.

    Returns ``FINALIZED`` if ``finalize`` was invoked (regardless of
    whether the stamping/storage step inside it succeeded — ``finalize``
    itself decides that and leaves ``status`` untouched on failure),
    ``NOT_PENDING`` if the submission isn't (or is no longer) ``"pending"``,
    or ``NOT_ALL_COMPLETED`` if some submitter still isn't ``"completed"``.

    ``populate_existing=True`` on the locked select is load-bearing, not
    decorative: every caller (``complete_signing`` via ``submitter.submission``,
    ``retry_completion`` via ``db.get``) has *already* loaded this same
    ``Submission`` into the session's identity map before calling here.
    Without ``populate_existing``, SQLAlchemy returns that same
    already-loaded Python object as-is and does **not** overwrite its
    attributes with the freshly queried row — so ``submission.status``
    below would still read whatever was cached *before* this ``FOR UPDATE``
    blocked and unblocked, not the value the lock just made current. That
    silently defeats the entire point of locking: a concurrent transaction
    could commit a status change while this call was blocked on the lock,
    and the stale cached object would never notice.
    """
    db.flush()
    submission = db.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()
    if submission.status != "pending":
        return FinalizeOutcome.NOT_PENDING

    still_open = db.scalar(
        select(func.count())
        .select_from(Submitter)
        .where(
            Submitter.submission_id == submission_id,
            # CC rows receive copies, never sign — they must not hold the
            # envelope open.
            Submitter.is_cc.is_(False),
            Submitter.status != "completed",
        ),
    )
    if still_open != 0:
        return FinalizeOutcome.NOT_ALL_COMPLETED

    finalize(db, submission_id, storage)
    return FinalizeOutcome.FINALIZED
