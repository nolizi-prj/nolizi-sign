"""SQLAlchemy ORM models. Founding design: docs/superpowers/specs/2026-07-30-internal-esign-design.md
(since extended: external signers, sender roles, ordered signing, CC recipients, per-user archive)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SUBMISSION_STATUSES = ("draft", "pending", "completed", "cancelled", "declined", "expired")
SUBMITTER_STATUSES = ("pending", "opened", "completed", "declined")
AUDIT_EVENTS = (
    "created",
    "sent",
    "opened",
    "signed",
    "reminded",
    "completed",
    "cancelled",
    "declined",
    "corrected",
    "expired",
)


class User(Base):
    """A person who can sign or send documents, provisioned on first Entra login."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entra_oid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # External signer: has no login of any kind — their only access path is a
    # signed token link scoped to one submitter (see routers/signing.py).
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Send permission, admin-revocable. Not itself a security boundary for
    # external users — the guard (require_sender) also excludes is_external,
    # so this column can stay True on an external row without granting them
    # anything.
    can_send: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Magic-link single-use floor: email-login tokens issued at or before this
    # instant are rejected (set to the token's issue time on each such login).
    email_login_min_iat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Template(Base):
    """A reusable (or single-use ad-hoc) document with defined signable fields."""

    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    original_file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    pdf_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_adhoc: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Owner-controlled: a shared template is visible and sendable (read-only)
    # to every sender; editing/archiving/toggling stay owner-or-admin.
    shared: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[User] = relationship(foreign_keys=[created_by])


class Submission(Base):
    """A single "send" of a template to one or more signers."""

    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(f"status IN {SUBMISSION_STATUSES}", name="ck_submissions_status"),
        Index("ix_submissions_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Random, non-enumerable ID stamped on externally shared artifacts
    # (watermark, certificate) instead of the sequential PK, so recipients
    # can't infer envelope volume. PK stays for routes/FKs/storage keys.
    public_uid: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        default=lambda: uuid.uuid4().hex,
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Sender-chosen deadline (NULL = never expires). The daily sweep flips
    # past-due pending envelopes to "expired"; signing routes reject past-due
    # envelopes immediately, without waiting for the sweep.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the "expiring soon" warning was sent — the sweep's send-once marker.
    expiry_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-envelope reminder policy (DocuSign-style): the daily sweep skips
    # envelopes with reminders off and paces the rest by their own interval.
    # Manual remind ignores both — the sender explicitly asked. Defaults
    # reproduce the original hard-coded policy (on, every 3 days).
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    reminder_interval_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    signed_pdf_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Standalone signature-certificate PDF (issue #15). NULL for envelopes
    # completed before the certificate became its own artifact — those keep
    # the certificate page merged inside signed_pdf_key's document.
    certificate_pdf_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # SharePoint archive mirror (docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md).
    # archived_at NULL + status 'completed' = "still needs archiving" (the
    # daily sweep's retry predicate); archive_url is the folder webUrl.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # The archive folder this envelope claimed (set on the first attempt,
    # before any upload): names carry no unique id anymore, so a name
    # collision gets a "_2" suffix — and retries of a partially-failed
    # archive must land back in *their own* claimed folder, never mint a
    # fresh suffix against their own leftovers.
    archive_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    template: Mapped[Template] = relationship(foreign_keys=[template_id])
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    submitters: Mapped[list["Submitter"]] = relationship(back_populates="submission", cascade="all, delete-orphan")


class Submitter(Base):
    """A single signer's participation in a submission."""

    __tablename__ = "submitters"
    __table_args__ = (
        CheckConstraint(f"status IN {SUBMITTER_STATUSES}", name="ck_submitters_status"),
        Index("ix_submitters_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    # Signing-order group: submitters with equal order_index sign in
    # parallel; a submitter may only sign once every lower group completed.
    # 0 for everyone = today's all-at-once behavior.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # CC recipient (DocuSign "receives a copy"): emailed a copy when routing
    # reaches their order group and the final PDF at completion; never signs,
    # never blocks completion, and holds no signable fields (role is "").
    is_cc: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="pending")
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    email_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # When this recipient's first email about the envelope was attempted —
    # the reminder overdue-clock's reference point. NULL until their order
    # group becomes due (submission.created_at stands in for legacy rows).
    first_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # External signing (docs/superpowers/specs/2026-08-01-external-signers-design.md):
    # access_uid is the random secret in an external signer's emailed link
    # (NULL for internal signers); the verification_* columns hold the current
    # emailed 6-digit code (sha256 hex), its expiry, and failed-attempt count.
    access_uid: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    verification_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    submission: Mapped[Submission] = relationship(back_populates="submitters")
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class SubmissionArchive(Base):
    """A per-user "hide this envelope from my views" marker.

    DocuSign-style delete-is-hide: archiving never touches the envelope,
    its files, its audit trail, or any other participant's view — it only
    filters the envelope out of the archiving user's own lists. Rows are
    created/removed by the archive/unarchive endpoints; uniqueness makes
    both idempotent.
    """

    __tablename__ = "submission_archives"
    __table_args__ = (UniqueConstraint("submission_id", "user_id", name="uq_submission_archives_submission_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attachment(Base):
    """A file a signer uploaded for an ``attachment`` field.

    Scoped to one submitter row (not the user): using an attachment id on a
    different envelope is rejected at completion time, and replacing a signer
    cascades the old signer's uploads away with the row's reset. The file
    itself lives under ``attachments/{submitter_id}/`` in storage and is
    appended to the signed PDF at completion.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submitter_id: Mapped[int] = mapped_column(
        ForeignKey("submitters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submitter: Mapped[Submitter] = relationship(foreign_keys=[submitter_id])


class Signature(Base):
    """A stored signature image for a user, reused across submitters."""

    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    image_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class AuditEvent(Base):
    """An append-only audit trail entry for a submission. No update/delete paths."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(f"event IN {AUDIT_EVENTS}", name="ck_audit_events_event"),
        Index("ix_audit_events_submission_id", "submission_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submission: Mapped[Submission] = relationship(foreign_keys=[submission_id])
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_user_id])
