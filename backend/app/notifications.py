"""Email notification hooks: submission created, completed, and reminders.

Every function here takes ``settings`` explicitly (mirroring Task 7's
pattern for ``storage``) since Graph delivery config and ``app_base_url``
(used to build signing links) live there — nothing in this module reads a
global ``Settings`` singleton. Callers (the submissions router,
``completion.finalize``, the jobs router) all already have ``settings``
available via ``Depends(get_settings)``.

None of these functions ever raise on a mail failure — ``mailer.send``
already swallows and returns ``bool``, and this module never re-raises on
top of that. Failures are logged with submission/submitter ids only (never
message bodies, addresses beyond what's already routed to Graph, or
tokens — see ``mailer``'s docstring).
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import audit, mailer
from app.config import Settings
from app.models import Submission, Submitter, User
from app.sharepoint import artifact_filename
from app.storage import FileStorage

logger = logging.getLogger(__name__)

# Reminder policy constants (not settings — the brief fixes these values).
REMINDER_MIN_DAYS = 3
REMINDER_MAX = 3

# How close to its deadline an envelope must be before the "expiring soon"
# warning goes out (DocuSign's expire-warn equivalent).
EXPIRY_WARNING_DAYS = 2

_BUTTON_STYLE = (
    "display:inline-block;padding:10px 20px;background:#1C3A62;color:#ffffff;"
    "text-decoration:none;border-radius:6px;font-family:sans-serif;"
)


def _sign_link(settings: Settings, submitter: Submitter) -> str:
    """Personal signing URL: token link for external signers, plain id link
    (behind login) for internal ones."""
    if submitter.access_uid:
        return f"{settings.app_base_url}/sign/t/{submitter.access_uid}"
    return f"{settings.app_base_url}/sign/{submitter.id}"


def _request_email_html(sender_name: str, title: str, message: str | None, link: str) -> str:
    """HTML body for a "please sign" (or reminder) email. All user content is HTML-escaped."""
    parts = [
        f"<p>{html.escape(sender_name)} has requested your signature on <strong>{html.escape(title)}</strong>.</p>",
    ]
    if message:
        parts.append(f"<p>{html.escape(message)}</p>")
    safe_link = html.escape(link)
    parts.append(f'<p><a href="{safe_link}" style="{_BUTTON_STYLE}">Review &amp; sign</a></p>')
    return "\n".join(parts)


def _resolve_user(db: Session, submitter: Submitter) -> User | None:
    return submitter.user if submitter.user is not None else db.get(User, submitter.user_id)


def send_sign_request(db: Session, submitter: Submitter, submission: Submission, settings: Settings) -> None:
    """Email one submitter a "please sign" request; sets ``submitter.email_status``.

    Extracted out of ``on_submission_created`` (which calls this once per
    submitter) so the "replace a signer" route (``PUT
    /api/submissions/{id}/submitters/{submitter_id}``) can send the same
    request to just the one newly-assigned submitter, instead of
    duplicating the email body/subject logic.
    """
    sender = db.get(User, submission.created_by)
    sender_name = sender.name if sender else "Someone"
    subject = f"{sender_name} requests your signature: {submission.title}"

    user = _resolve_user(db, submitter)
    if user is None:
        submitter.email_status = "failed"
        return

    link = _sign_link(settings, submitter)
    body = _request_email_html(sender_name, submission.title, submission.message, link)
    ok = mailer.send(settings, [user.email], subject, body)
    submitter.email_status = "sent" if ok else "failed"
    if submitter.first_notified_at is None:
        # The reminder overdue-clock starts at the first send *attempt* —
        # not submission.created_at, which punishes later order groups.
        submitter.first_notified_at = datetime.now(UTC)
    if not ok:
        logger.warning(
            "Failed to send sign-request email for submission_id=%s submitter_id=%s",
            submission.id,
            submitter.id,
        )


def active_order(submission: Submission) -> int | None:
    """The routing group whose turn it is: the minimum ``order_index`` among
    non-completed *signers* (CC rows never gate routing), or None when every
    signer has signed."""
    pending = [s.order_index for s in submission.submitters if not s.is_cc and s.status != "completed"]
    return min(pending) if pending else None


def recipient_due(submission: Submission, submitter: Submitter) -> bool:
    """Whether routing has reached ``submitter``'s group: every *signer* in a
    lower group has completed. Holds for signers ("your turn to sign") and
    CC rows ("here's your copy") alike."""
    return all(
        peer.status == "completed"
        for peer in submission.submitters
        if not peer.is_cc and peer.order_index < submitter.order_index
    )


def send_copy_notice(db: Session, submitter: Submitter, submission: Submission, settings: Settings) -> None:
    """Email a CC recipient that a copy of the envelope is on its way to them."""
    sender = db.get(User, submission.created_by)
    sender_name = sender.name if sender else "Someone"
    user = _resolve_user(db, submitter)
    if user is None:
        submitter.email_status = "failed"
        return

    subject = f"{sender_name} sent you a copy: {submission.title}"
    parts = [
        f"<p>{html.escape(sender_name)} is collecting signatures on "
        f"<strong>{html.escape(submission.title)}</strong> and has added you as a copy recipient.</p>",
    ]
    if submission.message:
        parts.append(f"<p>{html.escape(submission.message)}</p>")
    parts.append(
        "<p>You'll receive the final signed PDF by email once everyone has signed. Nothing is needed from you.</p>",
    )
    ok = mailer.send(settings, [user.email], subject, "\n".join(parts))
    submitter.email_status = "sent" if ok else "failed"
    if submitter.first_notified_at is None:
        submitter.first_notified_at = datetime.now(UTC)
    if not ok:
        logger.warning(
            "Failed to send CC copy notice for submission_id=%s submitter_id=%s",
            submission.id,
            submitter.id,
        )


def send_recipient_email(db: Session, submitter: Submitter, submission: Submission, settings: Settings) -> None:
    """The right first-contact email for a recipient row: sign request for
    signers, copy notice for CC rows."""
    if submitter.is_cc:
        send_copy_notice(db, submitter, submission, settings)
    else:
        send_sign_request(db, submitter, submission, settings)


def on_submission_created(db: Session, submission: Submission, settings: Settings) -> None:
    """Email every recipient whose routing group is due at send time; sets ``email_status``.

    Called from ``routers/submissions.py`` *after* the submission and all
    its submitters have been created and committed — for both the
    template-based and ad-hoc creation paths — so a slow/hung Graph send
    can never block or fail the create transaction itself. Since this
    mutates ``submitter.email_status``, the caller commits again afterward
    (a small, separate commit) to persist it.

    Later-order recipients keep ``email_status = NULL`` ("not yet asked") —
    ``on_submitter_completed`` emails them when their group becomes due.
    """
    for submitter in submission.submitters:
        if recipient_due(submission, submitter):
            send_recipient_email(db, submitter, submission, settings)


def on_submitter_completed(db: Session, submission: Submission, settings: Settings) -> None:
    """Email newly-due recipients after a completion that didn't finish the envelope.

    Idempotent by design: only recipients whose ``email_status`` is still
    NULL — i.e. never contacted — get an email, so a second call (a parallel
    co-signer in the same group finishing) sends nothing. Signers get the
    sign request, CC rows the copy notice. The caller commits afterward to
    persist ``email_status``, same contract as ``on_submission_created``.
    """
    for submitter in submission.submitters:
        if submitter.status != "completed" and submitter.email_status is None and recipient_due(submission, submitter):
            send_recipient_email(db, submitter, submission, settings)


def on_submission_completed(db: Session, submission: Submission, storage: FileStorage, settings: Settings) -> None:
    """Email every submitter + the sender (deduped) that the submission is fully signed.

    Called by the router (the last signer's ``/complete``, or
    ``POST /api/submissions/{id}/retry-completion``) *after* that request's
    own ``db.commit()`` — never from inside ``completion.finalize``/
    ``finalize_if_ready``, which run under a row lock; see ``completion``'s
    module docstring for why. Callers only reach here once they've
    confirmed (post-commit) that ``submission.status == "completed"``, so
    ``submission.signed_pdf_key`` is set. Attaches the signed PDF, read via
    ``storage.open``; if it can't be read (should be unreachable given that
    precondition), the email is still sent without an attachment rather
    than dropped.
    """
    internal: dict[str, None] = {}
    external: dict[str, None] = {}
    for submitter in submission.submitters:
        user = _resolve_user(db, submitter)
        if user is not None:
            (external if user.is_external else internal).setdefault(user.email, None)

    sender = db.get(User, submission.created_by)
    if sender is not None:
        internal.setdefault(sender.email, None)
    for email in internal:
        external.pop(email, None)

    if not internal and not external:
        return

    attachments: list[tuple[str, bytes, str]] = []
    if submission.signed_pdf_key:
        try:
            pdf_bytes = storage.open(submission.signed_pdf_key)
        except FileNotFoundError:
            logger.warning("Signed PDF missing in storage for submission_id=%s", submission.id)
        else:
            # Same name as the SharePoint archive copy and the portal download
            # (``{UTC date} {title} - signed.pdf``) — non-ASCII titles survive.
            filename = artifact_filename(
                submission.title,
                submission.completed_at or datetime.now(UTC),
                "signed",
            )
            attachments.append((filename, pdf_bytes, "application/pdf"))

    subject = f"Completed: {submission.title}"
    base_body = (
        f"<p>The document <strong>{html.escape(submission.title)}</strong> "
        "has been signed by all parties. The signed PDF is attached.</p>"
    )
    envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
    internal_body = (
        base_body + f'<p><a href="{envelope_link}">View the envelope\'s history and signature certificate</a></p>'
    )

    ok = True
    if internal:
        ok = mailer.send(settings, list(internal), subject, internal_body, attachments) and ok
    if external:
        # No portal link — /envelopes/{id} requires a login externals don't have.
        ok = mailer.send(settings, list(external), subject, base_body, attachments) and ok
    if not ok:
        logger.warning("Failed to send completion email for submission_id=%s", submission.id)


def on_submission_cancelled(
    db: Session,
    submission: Submission,
    actor: User,
    settings: Settings,
    reason: str | None,
) -> None:
    """Email everyone who had been contacted about the envelope that it was voided.

    Recipients: every submitter (signer or CC) whose ``email_status`` is set
    — i.e. an email about this envelope was at least attempted — plus the
    sender when an admin voided on their behalf. Never-contacted recipients
    (later order groups) hear nothing: they never knew the envelope existed.
    The actor themselves is skipped. Called by the cancel route *after* its
    own ``db.commit()``, same contract as ``on_submission_completed``.
    """
    internal: dict[str, None] = {}
    external: dict[str, None] = {}
    for submitter in submission.submitters:
        if submitter.email_status is None:
            continue
        user = _resolve_user(db, submitter)
        if user is not None and user.id != actor.id:
            (external if user.is_external else internal).setdefault(user.email, None)

    sender = db.get(User, submission.created_by)
    if sender is not None and sender.id != actor.id:
        internal.setdefault(sender.email, None)
    for email in internal:
        external.pop(email, None)

    if not internal and not external:
        return

    subject = f"Voided: {submission.title}"
    parts = [
        f"<p><strong>{html.escape(actor.name)}</strong> has voided the envelope "
        f"<strong>{html.escape(submission.title)}</strong>. "
        "It can no longer be signed, and any signatures already collected on it are void.</p>",
    ]
    if reason:
        parts.append(f"<p>Reason: {html.escape(reason)}</p>")
    parts.append("<p>No further action is needed from you.</p>")
    base_body = "\n".join(parts)
    envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
    internal_body = base_body + f'\n<p><a href="{envelope_link}">View the envelope</a></p>'

    ok = True
    if internal:
        ok = mailer.send(settings, list(internal), subject, internal_body) and ok
    if external:
        # No portal link — /envelopes/{id} requires a login externals don't have.
        ok = mailer.send(settings, list(external), subject, base_body) and ok
    if not ok:
        logger.warning("Failed to send void email for submission_id=%s", submission.id)


def on_submission_expired(db: Session, submission: Submission, settings: Settings) -> None:
    """Email the sender and every already-contacted recipient that the envelope
    expired unsigned. Same contacted-party fan-out as ``on_submission_cancelled``
    (never-contacted later groups hear nothing), but with no acting user —
    the deadline itself did this."""
    internal: dict[str, None] = {}
    external: dict[str, None] = {}
    for submitter in submission.submitters:
        if submitter.email_status is None:
            continue
        user = _resolve_user(db, submitter)
        if user is not None:
            (external if user.is_external else internal).setdefault(user.email, None)

    sender = db.get(User, submission.created_by)
    if sender is not None:
        internal.setdefault(sender.email, None)
    for email in internal:
        external.pop(email, None)

    if not internal and not external:
        return

    subject = f"Expired: {submission.title}"
    base_body = (
        f"<p>The envelope <strong>{html.escape(submission.title)}</strong> reached its expiration date "
        f"before everyone signed. It can no longer be signed, and any signatures already collected "
        "on it are void.</p>"
        "<p>No further action is needed from you. The sender can send a new envelope if one is "
        "still required.</p>"
    )
    envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
    internal_body = base_body + f'\n<p><a href="{envelope_link}">View the envelope</a></p>'

    ok = True
    if internal:
        ok = mailer.send(settings, list(internal), subject, internal_body) and ok
    if external:
        # No portal link — /envelopes/{id} requires a login externals don't have.
        ok = mailer.send(settings, list(external), subject, base_body) and ok
    if not ok:
        logger.warning("Failed to send expired email for submission_id=%s", submission.id)


def run_expirations(db: Session, settings: Settings) -> int:
    """Flip every past-due pending envelope to "expired" (+ audit event + emails).

    Called from ``POST /api/jobs/daily`` before the reminder sweep, so a
    just-expired envelope isn't also reminded about. The caller commits.
    Mail goes out per envelope right after its status flip — the daily job
    holds no row locks, so the "no mail under a lock" rule doesn't bite here.
    """
    now = datetime.now(UTC)
    due = db.scalars(
        select(Submission)
        .options(selectinload(Submission.submitters).selectinload(Submitter.user))
        .where(Submission.status == "pending", Submission.expires_at.is_not(None), Submission.expires_at <= now),
    ).all()
    for submission in due:
        submission.status = "expired"
        audit.record(db, submission.id, "expired", actor_user_id=None)
        on_submission_expired(db, submission, settings)
    return len(due)


def send_expiry_warnings(db: Session, settings: Settings) -> int:
    """Warn, once per envelope, that its deadline is EXPIRY_WARNING_DAYS or less away.

    Recipients: every contacted, not-yet-completed signer (the people who can
    still act) plus the sender. ``expiry_warned_at`` is set unconditionally —
    like the reminder bookkeeping, a failing address must not be retried
    daily forever. The caller commits.
    """
    now = datetime.now(UTC)
    window_end = now + timedelta(days=EXPIRY_WARNING_DAYS)
    expiring = db.scalars(
        select(Submission)
        .options(selectinload(Submission.submitters).selectinload(Submitter.user))
        .where(
            Submission.status == "pending",
            Submission.expires_at.is_not(None),
            Submission.expires_at > now,
            Submission.expires_at <= window_end,
            Submission.expiry_warned_at.is_(None),
        ),
    ).all()

    for submission in expiring:
        deadline = _iso_date(submission.expires_at)
        subject = f"Expiring soon: {submission.title}"
        signer_body_intro = (
            f"<p>The envelope <strong>{html.escape(submission.title)}</strong> expires on "
            f"<strong>{deadline}</strong>. After that it can no longer be signed.</p>"
        )
        for submitter in submission.submitters:
            if submitter.is_cc or submitter.status == "completed" or submitter.email_status is None:
                continue
            user = _resolve_user(db, submitter)
            if user is None:
                continue
            link = html.escape(_sign_link(settings, submitter))
            body = "\n".join(
                [
                    signer_body_intro,
                    f'<p><a href="{link}" style="{_BUTTON_STYLE}">Review &amp; sign</a></p>',
                ],
            )
            if not mailer.send(settings, [user.email], subject, body):
                logger.warning(
                    "Failed to send expiry warning for submission_id=%s submitter_id=%s",
                    submission.id,
                    submitter.id,
                )

        sender = db.get(User, submission.created_by)
        if sender is not None:
            envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
            sender_body = (
                f"<p>Your envelope <strong>{html.escape(submission.title)}</strong> expires on "
                f"<strong>{deadline}</strong> and hasn't been signed by everyone yet.</p>"
                f'<p><a href="{envelope_link}">View the envelope</a></p>'
            )
            if not mailer.send(settings, [sender.email], subject, sender_body):
                logger.warning("Failed to send expiry warning to sender for submission_id=%s", submission.id)

        submission.expiry_warned_at = now
    return len(expiring)


def _iso_date(value: datetime | None) -> str:
    if value is None:
        return "N/A"
    dt = value if value.tzinfo else value.replace(tzinfo=UTC)
    return dt.astimezone(UTC).date().isoformat()


def on_submission_declined(db: Session, submission: Submission, submitter: Submitter, settings: Settings) -> None:
    """Email everyone affected that a signer declined (with their reason, if given).

    A decline voids the whole envelope, so the fan-out matches
    ``on_submission_cancelled``: the sender plus every already-contacted
    submitter — co-signers mid-flow, signers whose collected signatures are
    now void, CC recipients waiting on the final PDF — except the decliner
    themselves. Externals get no portal link, same split as everywhere else.
    """
    signer = _resolve_user(db, submitter)
    signer_name = signer.name if signer else "A signer"

    internal: dict[str, None] = {}
    external: dict[str, None] = {}
    for peer in submission.submitters:
        if peer.id == submitter.id or peer.email_status is None:
            continue
        user = _resolve_user(db, peer)
        if user is not None:
            (external if user.is_external else internal).setdefault(user.email, None)
    sender = db.get(User, submission.created_by)
    if sender is not None:
        internal.setdefault(sender.email, None)
    for email in internal:
        external.pop(email, None)
    if signer is not None:
        internal.pop(signer.email, None)
        external.pop(signer.email, None)

    if not internal and not external:
        return

    parts = [
        f"<p><strong>{html.escape(signer_name)}</strong> has declined to sign "
        f"<strong>{html.escape(submission.title)}</strong>. The envelope is now void.</p>",
    ]
    if submitter.decline_reason:
        parts.append(f"<p>Reason: {html.escape(submitter.decline_reason)}</p>")
    base_body = "\n".join(parts)
    envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
    internal_body = base_body + f'\n<p><a href="{envelope_link}">View the envelope</a></p>'

    subject = f"Declined: {submission.title}"
    ok = True
    if internal:
        ok = mailer.send(settings, list(internal), subject, internal_body) and ok
    if external:
        ok = mailer.send(settings, list(external), subject, base_body) and ok
    if not ok:
        logger.warning("Failed to send decline email for submission_id=%s", submission.id)


def on_document_replaced(db: Session, submission: Submission, actor: User, settings: Settings) -> None:
    """Email already-contacted signers that the envelope's document was swapped.

    The replace-document endpoint only runs while nobody has signed, so the
    audience is exactly the contacted, not-yet-completed signers — the
    people who may have read (or be holding a tab open on) the old version.
    Each gets their personal sign link again. CC rows wait for the final
    PDF and don't act on the document, so they're not re-notified.
    """
    subject = f"Document updated: {submission.title}"
    for submitter in submission.submitters:
        if submitter.is_cc or submitter.status == "completed" or submitter.email_status is None:
            continue
        user = _resolve_user(db, submitter)
        if user is None:
            continue
        link = html.escape(_sign_link(settings, submitter))
        body = "\n".join(
            [
                f"<p><strong>{html.escape(actor.name)}</strong> has replaced the document in "
                f"<strong>{html.escape(submission.title)}</strong>.</p>",
                "<p>If you already reviewed it, please review the new version before signing — "
                "any copy you saved or left open is out of date.</p>",
                f'<p><a href="{link}" style="{_BUTTON_STYLE}">Review &amp; sign</a></p>',
            ],
        )
        if not mailer.send(settings, [user.email], subject, body):
            logger.warning(
                "Failed to send document-replaced email for submission_id=%s submitter_id=%s",
                submission.id,
                submitter.id,
            )


def on_submitter_removed(db: Session, submission: Submission, removed_user: User, settings: Settings) -> None:
    """Tell a swapped-out signer they're off the envelope and their link is dead.

    Their emailed sign link 404s the moment the replacement lands (the
    access_uid is regenerated) — without this note, an external counterparty
    is left with what looks like a broken or phishy link and no explanation.
    Only called when the removed signer had actually been contacted.
    """
    body = (
        f"<p>You have been removed as a signer on <strong>{html.escape(submission.title)}</strong>. "
        "No action is needed from you, and your signing link no longer works.</p>"
    )
    if not mailer.send(settings, [removed_user.email], f"Removed from: {submission.title}", body):
        logger.warning("Failed to send removed-signer email for submission_id=%s", submission.id)


def _is_overdue(submitter: Submitter, min_days: int) -> bool:
    """Whether ``submitter`` is due for a reminder: ``now - max(first contact, last_reminded_at) >= min_days``.

    The reference is ``first_notified_at`` — when this submitter's first
    email was actually attempted — so an ordered-signing group-2 signer who
    was first contacted on day 8 isn't instantly "8 days overdue".
    ``submission.created_at`` remains the fallback for legacy rows created
    before the column existed (backfilled equal for group-1 rows anyway).
    """
    if min_days <= 0:
        # No wait to enforce (the sender-triggered /remind path), so skip the
        # clock comparison entirely: ``created_at`` is stamped by Postgres's
        # clock, which can sit a sub-second ahead of the app clock and would
        # make a brand-new submitter randomly "not yet due".
        return True
    reference = submitter.first_notified_at or submitter.submission.created_at
    if submitter.last_reminded_at is not None and submitter.last_reminded_at > reference:
        reference = submitter.last_reminded_at
    return datetime.now(UTC) - reference >= timedelta(days=min_days)


def _eligible_submitters(db: Session, min_days: int | None, *, submission_id: int | None = None) -> list[Submitter]:
    """Submitters eligible for a reminder: pending/opened, submission pending, cap not hit, overdue.

    ``min_days=None`` is the daily sweep: each envelope's own
    ``reminder_interval_days`` paces its reminders, and envelopes with
    ``reminders_enabled`` off are excluded. An explicit ``min_days`` is the
    manual-remind path (0 = the sender explicitly asked), which ignores both
    per-envelope settings.

    Status/submission/cap filters happen in SQL, in a single query (per the
    controller decision, ``run_daily_reminders`` must use one query across
    all pending submissions rather than one per submission); the day-based
    "overdue" check is applied in Python via ``_is_overdue`` afterward,
    since it needs a ``max(a, b)`` against a possibly-NULL column that's
    simpler and more portably correct to compute here than as a
    cross-dialect SQL expression.
    """
    stmt = (
        select(Submitter)
        .join(Submission, Submitter.submission_id == Submission.id)
        .options(
            selectinload(Submitter.submission).selectinload(Submission.submitters),
            selectinload(Submitter.user),
        )
        .where(
            Submitter.status.in_(("pending", "opened")),
            Submitter.is_cc.is_(False),
            Submission.status == "pending",
            Submitter.reminder_count < REMINDER_MAX,
        )
    )
    if min_days is None:
        stmt = stmt.where(Submission.reminders_enabled.is_(True))
    if submission_id is not None:
        stmt = stmt.where(Submission.id == submission_id)
    return [
        s
        for s in db.scalars(stmt)
        # Never remind someone whose turn hasn't come (ordered signing).
        if s.order_index == active_order(s.submission)
        and _is_overdue(s, s.submission.reminder_interval_days if min_days is None else min_days)
    ]


def _send_reminder(db: Session, submitter: Submitter, submission: Submission, settings: Settings) -> None:
    """Send one reminder email and record its bookkeeping, regardless of delivery success.

    ``last_reminded_at``/``reminder_count``/the ``reminded`` audit event are
    updated unconditionally (not gated on ``mailer.send``'s return value) so
    a persistently-failing address (bad email, mail outage) still counts
    against the reminder cap instead of being retried forever on every
    subsequent daily job run.
    """
    sender = db.get(User, submission.created_by)
    sender_name = sender.name if sender else "Someone"
    user = _resolve_user(db, submitter)

    if user is not None:
        link = _sign_link(settings, submitter)
        subject = f"Reminder: {sender_name} requests your signature: {submission.title}"
        body = _request_email_html(sender_name, submission.title, submission.message, link)
        ok = mailer.send(settings, [user.email], subject, body)
        if not ok:
            logger.warning(
                "Failed to send reminder email for submission_id=%s submitter_id=%s",
                submission.id,
                submitter.id,
            )

    submitter.last_reminded_at = datetime.now(UTC)
    submitter.reminder_count += 1
    audit.record(db, submission.id, "reminded", actor_user_id=None, submitter_id=submitter.id)


def send_reminders_for(
    db: Session,
    submission: Submission,
    settings: Settings,
    min_days: int = REMINDER_MIN_DAYS,
) -> int:
    """Send reminders to every eligible submitter on ``submission``. Returns the count sent.

    Called from ``POST /api/submissions/{id}/remind`` (sender-triggered,
    which passes ``min_days=0`` to bypass the 3-day wait — the sender
    explicitly asked — while still respecting the reminder cap and status
    rules) and, indirectly via ``run_daily_reminders``, by the daily job.
    """
    submitters = _eligible_submitters(db, min_days, submission_id=submission.id)
    for submitter in submitters:
        _send_reminder(db, submitter, submission, settings)
    return len(submitters)


def run_daily_reminders(db: Session, settings: Settings) -> int:
    """Send reminders to every eligible submitter across all pending submissions. Returns the count sent.

    The daily sweep: each envelope's own ``reminders_enabled`` /
    ``reminder_interval_days`` settings drive eligibility (``min_days=None``),
    evaluated with a single query across all submissions rather than one
    query per submission. Called from ``POST /api/jobs/daily``.
    """
    submitters = _eligible_submitters(db, None)
    for submitter in submitters:
        _send_reminder(db, submitter, submitter.submission, settings)
    return len(submitters)
