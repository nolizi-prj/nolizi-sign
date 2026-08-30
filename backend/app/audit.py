"""Append-only audit trail writer for submissions.

This module is the sole writer of ``audit_events`` rows — nothing else in
the codebase should insert into that table, and nothing ever updates or
deletes a row once written.

``record`` flushes the new row (so it gets an id and becomes visible to
later queries within the same transaction) but deliberately does **not**
commit. The caller owns the transaction boundary: a submission-creation
request that writes several audit events (one ``created`` + one ``sent`` per
submitter) commits once at the end, so a failure partway through rolls back
the audit trail along with everything else rather than leaving orphaned
events for a submission that was never actually created.
"""

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(
    db: Session,
    submission_id: int,
    event: str,
    *,
    actor_user_id: int | None = None,
    ip: str | None = None,
    detail: dict[str, object] | None = None,
    **extra: object,
) -> AuditEvent:
    """Insert (and flush, but not commit) an ``AuditEvent`` row.

    ``event`` must be one of ``models.AUDIT_EVENTS``; the database's check
    constraint enforces this on flush. The event's JSONB ``detail`` is built
    from ``detail`` (an explicit payload, e.g. ``detail={"changed": [...]}``)
    merged with any ``**extra`` keyword arguments (the older calling
    convention, e.g. ``submitter_id=5``) — both are supported so existing
    callers keep working unchanged.
    """
    payload: dict[str, object] = dict(detail) if detail else {}
    payload.update(extra)
    entry = AuditEvent(
        submission_id=submission_id,
        actor_user_id=actor_user_id,
        event=event,
        ip_address=ip,
        detail=payload,
    )
    db.add(entry)
    db.flush()
    return entry
