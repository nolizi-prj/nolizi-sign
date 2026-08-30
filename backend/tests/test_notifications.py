"""Tests for app.notifications: reminder eligibility, and created/completed email dispatch.

Reminder-eligibility scenarios build Submission/Submitter rows directly via
the ORM (not through the HTTP API) so ``Submission.created_at``/
``Submitter.last_reminded_at`` can be backdated — the API's create endpoint
always stamps ``created_at`` via the column's server default (``now()``).

Not listed among the brief's declared new test files (only
``test_mailer``/``test_jobs`` are), but the brief's own Step 1 explicitly
calls for a "reminder query test" matrix distinct from both — this is its
natural home, next to the module it tests.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.config import Settings
from app.models import AuditEvent, Submission, Submitter, Template, User

SETTINGS = Settings(app_base_url="http://testserver")


def _user(db: Session, email: str) -> User:
    user = User(email=email, name=email, is_admin=False)
    db.add(user)
    db.flush()
    return user


def _template(db: Session, creator: User) -> Template:
    template = Template(
        name="Doc",
        created_by=creator.id,
        original_file_key="x",
        pdf_key="x",
        page_count=1,
        fields=[
            {
                "id": "f1",
                "type": "signature",
                "role": "Signer 1",
                "page": 0,
                "x": 0.1,
                "y": 0.1,
                "w": 0.1,
                "h": 0.1,
                "required": True,
            },
        ],
    )
    db.add(template)
    db.flush()
    return template


def _submission(
    db: Session,
    *,
    sender: User,
    template: Template,
    created_at: datetime,
    status: str = "pending",
) -> Submission:
    submission = Submission(
        template_id=template.id,
        title="Contract",
        status=status,
        created_by=sender.id,
        created_at=created_at,
    )
    db.add(submission)
    db.flush()
    return submission


def _submitter(
    db: Session,
    *,
    submission: Submission,
    user: User,
    status: str = "pending",
    last_reminded_at: datetime | None = None,
    reminder_count: int = 0,
    role: str = "Signer 1",
    order_index: int = 0,
    email_status: str | None = None,
    is_cc: bool = False,
) -> Submitter:
    submitter = Submitter(
        submission_id=submission.id,
        user_id=user.id,
        role=role,
        status=status,
        last_reminded_at=last_reminded_at,
        reminder_count=reminder_count,
        order_index=order_index,
        email_status=email_status,
        is_cc=is_cc,
    )
    db.add(submitter)
    db.flush()
    return submitter


def _capture_sends(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        calls.append({"to": to, "subject": subject, "html": html_body, "attachments": attachments})
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)
    return calls


# --- reminder eligibility -------------------------------------------------


def test_run_daily_reminders_selects_only_eligible_submitters(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "sender@example.com")
    template = _template(db, sender)

    # Eligible: created 4 days ago, never reminded, under the cap.
    eligible_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=4))
    eligible_submitter = _submitter(db, submission=eligible_submission, user=_user(db, "eligible@example.com"))

    # Not eligible: reminded yesterday (gap since last reminder < 3 days).
    recent_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    recent_submitter = _submitter(
        db,
        submission=recent_submission,
        user=_user(db, "recent@example.com"),
        last_reminded_at=now - timedelta(days=1),
    )

    # Not eligible: reminder_count already at the cap.
    capped_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    capped_submitter = _submitter(
        db,
        submission=capped_submission,
        user=_user(db, "capped@example.com"),
        reminder_count=3,
    )

    # Not eligible: submission cancelled.
    cancelled_submission = _submission(
        db,
        sender=sender,
        template=template,
        created_at=now - timedelta(days=10),
        status="cancelled",
    )
    cancelled_submitter = _submitter(db, submission=cancelled_submission, user=_user(db, "cancelled@example.com"))

    db.commit()

    count = notifications.run_daily_reminders(db, SETTINGS)
    db.commit()

    assert count == 1

    db.refresh(eligible_submitter)
    db.refresh(recent_submitter)
    db.refresh(capped_submitter)
    db.refresh(cancelled_submitter)

    assert eligible_submitter.reminder_count == 1
    assert eligible_submitter.last_reminded_at is not None
    assert recent_submitter.reminder_count == 0
    assert capped_submitter.reminder_count == 3
    assert cancelled_submitter.reminder_count == 0

    events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.submission_id == eligible_submission.id,
            AuditEvent.event == "reminded",
        ),
    ).all()
    assert len(events) == 1
    assert events[0].actor_user_id is None
    assert events[0].detail == {"submitter_id": eligible_submitter.id}


def test_opened_submitter_status_is_eligible(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "sender-opened@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    _submitter(db, submission=submission, user=_user(db, "opened@example.com"), status="opened")
    db.commit()

    assert notifications.run_daily_reminders(db, SETTINGS) == 1


def test_completed_submitter_status_is_not_eligible(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "sender-done@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    _submitter(db, submission=submission, user=_user(db, "done@example.com"), status="completed")
    db.commit()

    assert notifications.run_daily_reminders(db, SETTINGS) == 0


def test_send_reminders_for_only_targets_its_own_submission(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "sender-scope@example.com")
    template = _template(db, sender)

    target_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=4))
    target_submitter = _submitter(db, submission=target_submission, user=_user(db, "target@example.com"))

    other_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=4))
    _submitter(db, submission=other_submission, user=_user(db, "other@example.com"))

    db.commit()

    count = notifications.send_reminders_for(db, target_submission, SETTINGS)
    db.commit()

    assert count == 1
    db.refresh(target_submitter)
    assert target_submitter.reminder_count == 1


def test_send_reminders_for_min_days_zero_bypasses_the_wait(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "sender-fresh@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now)
    submitter = _submitter(db, submission=submission, user=_user(db, "fresh@example.com"))
    db.commit()

    # Default 3-day minimum: a submission created "now" isn't due yet.
    assert notifications.send_reminders_for(db, submission, SETTINGS) == 0

    # min_days=0 (the manual /remind path) bypasses the wait.
    count = notifications.send_reminders_for(db, submission, SETTINGS, min_days=0)
    db.commit()

    assert count == 1
    db.refresh(submitter)
    assert submitter.reminder_count == 1


def test_send_reminders_for_min_days_zero_tolerates_db_clock_ahead(db: Session) -> None:
    """created_at comes from Postgres's clock, which can sit a sub-second
    ahead of the app clock (Docker/WSL2 drift) — putting a brand-new
    submission "in the future". A sender-triggered remind (min_days=0) has
    no wait to enforce, so it must not lose that clock race."""
    now = datetime.now(UTC)
    sender = _user(db, "sender-skew@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now + timedelta(seconds=2))
    submitter = _submitter(db, submission=submission, user=_user(db, "skew@example.com"))
    db.commit()

    count = notifications.send_reminders_for(db, submission, SETTINGS, min_days=0)
    db.commit()

    assert count == 1
    db.refresh(submitter)
    assert submitter.reminder_count == 1


# --- on_submission_created -------------------------------------------------


def test_on_submission_created_sets_sent_status_and_escapes_html(db: Session, monkeypatch) -> None:
    calls = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        calls.append({"to": to, "subject": subject, "html": html_body})
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)

    sender = _user(db, "boss@example.com")
    template = _template(db, sender)
    signer = _user(db, "signer@example.com")
    submission = Submission(
        template_id=template.id,
        title="<script>alert(1)</script>",
        message="hello & welcome",
        status="pending",
        created_by=sender.id,
    )
    db.add(submission)
    db.flush()
    submitter = Submitter(submission_id=submission.id, user_id=signer.id, role="Signer 1", status="pending")
    db.add(submitter)
    db.flush()
    db.refresh(submission)

    notifications.on_submission_created(db, submission, SETTINGS)

    assert submitter.email_status == "sent"
    assert len(calls) == 1
    assert calls[0]["to"] == ["signer@example.com"]
    assert calls[0]["subject"] == "boss@example.com requests your signature: <script>alert(1)</script>"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in calls[0]["html"]
    assert "hello &amp; welcome" in calls[0]["html"]
    assert f"http://testserver/sign/{submitter.id}" in calls[0]["html"]


def test_on_submission_created_sets_failed_status_on_send_failure(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(notifications.mailer, "send", lambda *a, **k: False)

    sender = _user(db, "boss2@example.com")
    template = _template(db, sender)
    signer = _user(db, "signer2@example.com")
    submission = Submission(template_id=template.id, title="Doc", status="pending", created_by=sender.id)
    db.add(submission)
    db.flush()
    submitter = Submitter(submission_id=submission.id, user_id=signer.id, role="Signer 1", status="pending")
    db.add(submitter)
    db.flush()
    db.refresh(submission)

    notifications.on_submission_created(db, submission, SETTINGS)

    assert submitter.email_status == "failed"


# --- signing order ----------------------------------------------------------


def test_on_submission_created_emails_only_first_order_group(db: Session, monkeypatch) -> None:
    calls = _capture_sends(monkeypatch)
    sender = _user(db, "order-sender@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC))
    first = _submitter(db, submission=submission, user=_user(db, "first@example.com"), order_index=0)
    second = _submitter(
        db,
        submission=submission,
        user=_user(db, "second@example.com"),
        role="Signer 2",
        order_index=1,
    )
    db.refresh(submission)

    notifications.on_submission_created(db, submission, SETTINGS)

    assert [c["to"] for c in calls] == [["first@example.com"]]
    assert first.email_status == "sent"
    assert second.email_status is None  # not asked yet — their turn hasn't come


def test_on_submitter_completed_emails_newly_active_group_once(db: Session, monkeypatch) -> None:
    calls = _capture_sends(monkeypatch)
    sender = _user(db, "unlock-sender@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC))
    _submitter(
        db,
        submission=submission,
        user=_user(db, "done@example.com"),
        status="completed",
        order_index=0,
        email_status="sent",
    )
    second = _submitter(
        db,
        submission=submission,
        user=_user(db, "next@example.com"),
        role="Signer 2",
        order_index=1,
    )
    db.refresh(submission)

    notifications.on_submitter_completed(db, submission, SETTINGS)

    assert [c["to"] for c in calls] == [["next@example.com"]]
    assert second.email_status == "sent"

    # Idempotent: calling again (e.g. a parallel co-signer in group 0 also
    # finishing) must not re-email the already-notified group.
    notifications.on_submitter_completed(db, submission, SETTINGS)
    assert len(calls) == 1


def test_reminders_skip_submitters_before_their_turn(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "turn-sender@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    waiting_first = _submitter(db, submission=submission, user=_user(db, "slow@example.com"), order_index=0)
    not_yet_turn = _submitter(
        db,
        submission=submission,
        user=_user(db, "later@example.com"),
        role="Signer 2",
        order_index=1,
    )
    db.refresh(submission)

    eligible = notifications._eligible_submitters(db, 3, submission_id=submission.id)

    assert waiting_first in eligible
    assert not_yet_turn not in eligible


# --- on_submission_completed -------------------------------------------------


class _FakeStorage:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def save(self, key: str, data: bytes) -> None:
        self.files[key] = data

    def open(self, key: str) -> bytes:
        return self.files[key]

    def exists(self, key: str) -> bool:
        return key in self.files

    def delete(self, key: str) -> None:
        self.files.pop(key, None)


def test_on_submission_completed_dedupes_recipients_and_attaches_signed_pdf(db: Session, monkeypatch) -> None:
    calls = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        calls.append({"to": to, "subject": subject, "body": html_body, "attachments": attachments})
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)

    # Sender is also the (only) submitter — should be deduped to one recipient.
    sender = _user(db, "shared@example.com")
    template = _template(db, sender)
    submission = Submission(
        template_id=template.id,
        title="Final Doc",
        status="completed",
        created_by=sender.id,
        signed_pdf_key="submissions/1/signed.pdf",
        completed_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    db.add(submission)
    db.flush()
    db.add(Submitter(submission_id=submission.id, user_id=sender.id, role="Signer 1", status="completed"))
    db.flush()
    db.refresh(submission)

    storage = _FakeStorage({"submissions/1/signed.pdf": b"%PDF-1.4 fake pdf bytes"})

    notifications.on_submission_completed(db, submission, storage, SETTINGS)

    assert len(calls) == 1
    assert calls[0]["to"] == ["shared@example.com"]
    assert calls[0]["subject"] == "Completed: Final Doc"
    filename, data, content_type = calls[0]["attachments"][0]
    # Same convention as the SharePoint archive and the portal download.
    assert filename == "2026-08-10 Final Doc - signed.pdf"
    assert data == b"%PDF-1.4 fake pdf bytes"
    assert content_type == "application/pdf"
    # The certificate is no longer merged into the signed PDF; the email links
    # to the envelope page, which holds the history + signature certificate.
    assert f"http://testserver/envelopes/{submission.id}" in calls[0]["body"]


def test_on_submission_completed_attachment_name_survives_korean_title(db: Session, monkeypatch) -> None:
    calls = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        calls.append({"attachments": attachments})
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)

    sender = _user(db, "korean@example.com")
    template = _template(db, sender)
    submission = Submission(
        template_id=template.id,
        title="콘토로로보틱스_근로계약서_법인장_안승열",
        status="completed",
        created_by=sender.id,
        signed_pdf_key="submissions/2/signed.pdf",
        completed_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    db.add(submission)
    db.flush()
    db.add(Submitter(submission_id=submission.id, user_id=sender.id, role="Signer 1", status="completed"))
    db.flush()
    db.refresh(submission)

    storage = _FakeStorage({"submissions/2/signed.pdf": b"%PDF korean"})
    notifications.on_submission_completed(db, submission, storage, SETTINGS)

    filename = calls[0]["attachments"][0][0]
    assert filename == "2026-08-10 콘토로로보틱스_근로계약서_법인장_안승열 - signed.pdf"


def test_on_submission_completed_includes_cc_submitters(db: Session, monkeypatch) -> None:
    calls = _capture_sends(monkeypatch)

    sender = _user(db, "cc-sender@example.com")
    template = _template(db, sender)
    submission = Submission(
        template_id=template.id,
        title="CC Doc",
        status="completed",
        created_by=sender.id,
        signed_pdf_key="submissions/9/signed.pdf",
    )
    db.add(submission)
    db.flush()
    db.add(Submitter(submission_id=submission.id, user_id=sender.id, role="Signer 1", status="completed"))
    cc_user = User(email="copy@example.com", name="Copy Person", is_admin=False, is_external=True)
    db.add(cc_user)
    db.flush()
    db.add(Submitter(submission_id=submission.id, user_id=cc_user.id, role="", is_cc=True, status="pending"))
    db.flush()
    db.refresh(submission)

    storage = _FakeStorage({"submissions/9/signed.pdf": b"%PDF fake"})
    notifications.on_submission_completed(db, submission, storage, SETTINGS)

    external_call = next(c for c in calls if "copy@example.com" in c["to"])
    # The external CC gets the attachment-only variant (no portal link).
    assert external_call["attachments"] is not None
    assert "/envelopes/" not in external_call["html"]


def test_cc_recipient_gets_copy_notice_when_due(db: Session, monkeypatch) -> None:
    """A CC in a middle order group is emailed a copy notice exactly when the
    signers below them finish — never a sign request, and never blocking the
    group after them."""
    calls = _capture_sends(monkeypatch)
    sender = _user(db, "routing-sender@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC))
    first = _submitter(db, submission=submission, user=_user(db, "first-signer@example.com"), order_index=0)
    cc = _submitter(
        db,
        submission=submission,
        user=_user(db, "middle-cc@example.com"),
        role="",
        order_index=1,
        is_cc=True,
    )
    last = _submitter(
        db,
        submission=submission,
        user=_user(db, "last-signer@example.com"),
        role="Signer 2",
        order_index=2,
    )
    db.refresh(submission)

    notifications.on_submission_created(db, submission, SETTINGS)
    assert [c["to"] for c in calls] == [["first-signer@example.com"]]
    assert cc.email_status is None

    first.status = "completed"
    db.flush()
    notifications.on_submitter_completed(db, submission, SETTINGS)

    # The CC copy notice and the next signer's request go out together: the
    # CC never gates the signer behind them.
    assert [c["to"] for c in calls[1:]] == [["middle-cc@example.com"], ["last-signer@example.com"]]
    cc_mail = calls[1]
    assert "copy" in cc_mail["subject"].lower()
    assert "sign/" not in cc_mail["html"]  # no signing link for CC
    assert cc.email_status == "sent"
    assert last.email_status == "sent"


def test_reminders_never_target_cc_recipients(db: Session) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "ccrem-sender@example.com")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    signer = _submitter(db, submission=submission, user=_user(db, "ccrem-signer@example.com"))
    cc = _submitter(
        db,
        submission=submission,
        user=_user(db, "ccrem-cc@example.com"),
        role="",
        is_cc=True,
        email_status="sent",
    )
    db.refresh(submission)

    eligible = notifications._eligible_submitters(db, 3, submission_id=submission.id)

    assert signer in eligible
    assert cc not in eligible


# --- external signer tests -------------------------------------------------


def test_request_email_uses_token_link_for_external(admin_client, db, monkeypatch) -> None:
    from tests.test_external_signing import _capture_mail, _external_submission

    sent = _capture_mail(monkeypatch)
    _submission, access_uid, _sid = _external_submission(admin_client, db)

    request_mail = next(m for m in sent if "requests your signature" in m["subject"])
    assert f"/sign/t/{access_uid}" in request_mail["body"]


def test_completion_email_to_externals_has_no_portal_link(
    admin_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    from tests.test_external_signing import _verified_anon
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL}).json()["signature_id"]
    anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig}})

    completion_mails = [m for m in sent if m["subject"].startswith("Completed:")]
    external = next(m for m in completion_mails if "ext@vendor.com" in m["to"])
    internal = next(m for m in completion_mails if "admin@pumasi.ai" in m["to"])
    assert "/envelopes/" not in external["body"]
    assert "/envelopes/" in internal["body"]
    assert external["attachments"] and internal["attachments"]


# --- void notification ------------------------------------------------------


def test_on_submission_cancelled_emails_contacted_recipients_only(db: Session, monkeypatch) -> None:
    """Void notifies everyone already contacted (signed or not, CC included,
    externals without a portal link) — and nobody who never heard of it."""
    now = datetime.now(UTC)
    sender = _user(db, "void-sender@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now)

    signed = _submitter(
        db,
        submission=submission,
        user=_user(db, "signed@pumasi.ai"),
        status="completed",
        email_status="sent",
    )
    pending = _submitter(db, submission=submission, user=_user(db, "pending@pumasi.ai"), email_status="sent")
    external_user = _user(db, "vendor@example.com")
    external_user.is_external = True
    _submitter(db, submission=submission, user=external_user, email_status="sent", role="Signer 2")
    cc = _submitter(
        db,
        submission=submission,
        user=_user(db, "cc@pumasi.ai"),
        email_status="sent",
        is_cc=True,
        role="",
    )
    # Order-group 2, never contacted — must hear nothing.
    _submitter(
        db,
        submission=submission,
        user=_user(db, "later@pumasi.ai"),
        order_index=1,
        email_status=None,
        role="Signer 3",
    )
    db.commit()

    sent = _capture_sends(monkeypatch)
    notifications.on_submission_cancelled(db, submission, sender, SETTINGS, "typo in the terms")

    assert len(sent) == 2  # one internal batch, one external batch
    internal = next(m for m in sent if "pending@pumasi.ai" in m["to"])
    external = next(m for m in sent if "vendor@example.com" in m["to"])
    assert set(internal["to"]) == {"signed@pumasi.ai", "pending@pumasi.ai", "cc@pumasi.ai"}
    assert internal["subject"] == "Voided: Contract"
    assert "typo in the terms" in internal["html"]
    assert "/envelopes/" in internal["html"]
    assert "/envelopes/" not in external["html"]
    assert signed is not None and pending is not None and cc is not None


def test_on_submission_cancelled_by_admin_notifies_sender(db: Session, monkeypatch) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "the-sender@pumasi.ai")
    admin = _user(db, "the-admin@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now)
    _submitter(db, submission=submission, user=_user(db, "signer@pumasi.ai"), email_status="sent")
    db.commit()

    sent = _capture_sends(monkeypatch)
    notifications.on_submission_cancelled(db, submission, admin, SETTINGS, None)

    assert len(sent) == 1
    assert set(sent[0]["to"]) == {"signer@pumasi.ai", "the-sender@pumasi.ai"}
    assert "the-admin@pumasi.ai" not in sent[0]["to"]
    assert "Reason:" not in sent[0]["html"]


# --- decline fan-out --------------------------------------------------------


def test_decline_notifies_all_contacted_parties_except_decliner(db: Session, monkeypatch) -> None:
    """Decline voids the envelope for everyone — co-signers mid-flow, signers
    who already signed, and CCs all hear about it, not just the sender."""
    now = datetime.now(UTC)
    sender = _user(db, "decline-sender@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now)

    _submitter(
        db,
        submission=submission,
        user=_user(db, "already-signed@pumasi.ai"),
        status="completed",
        email_status="sent",
    )
    decliner = _submitter(
        db,
        submission=submission,
        user=_user(db, "decliner@pumasi.ai"),
        status="declined",
        email_status="sent",
        role="Signer 2",
    )
    decliner.decline_reason = "terms unacceptable"
    _submitter(
        db,
        submission=submission,
        user=_user(db, "cc-decline@pumasi.ai"),
        email_status="sent",
        is_cc=True,
        role="",
    )
    _submitter(
        db,
        submission=submission,
        user=_user(db, "never-heard@pumasi.ai"),
        order_index=1,
        email_status=None,
        role="Signer 3",
    )
    db.commit()

    sent = _capture_sends(monkeypatch)
    notifications.on_submission_declined(db, submission, decliner, SETTINGS)

    assert len(sent) == 1
    assert set(sent[0]["to"]) == {"decline-sender@pumasi.ai", "already-signed@pumasi.ai", "cc-decline@pumasi.ai"}
    assert "terms unacceptable" in sent[0]["html"]


# --- reminder clock uses first contact --------------------------------------


def test_reminder_clock_starts_at_first_notified_at(db: Session) -> None:
    """A group-2 signer first contacted yesterday is not overdue, even on an
    old submission; one first contacted 4 days ago is."""
    now = datetime.now(UTC)
    sender = _user(db, "clock-sender@pumasi.ai")
    template = _template(db, sender)

    old_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    fresh_contact = _submitter(
        db,
        submission=old_submission,
        user=_user(db, "fresh-contact@pumasi.ai"),
        email_status="sent",
    )
    fresh_contact.first_notified_at = now - timedelta(days=1)

    other_submission = _submission(db, sender=sender, template=template, created_at=now - timedelta(days=10))
    stale_contact = _submitter(
        db,
        submission=other_submission,
        user=_user(db, "stale-contact@pumasi.ai"),
        email_status="sent",
    )
    stale_contact.first_notified_at = now - timedelta(days=4)
    db.commit()

    assert notifications.run_daily_reminders(db, SETTINGS) == 1
    db.refresh(fresh_contact)
    db.refresh(stale_contact)
    assert fresh_contact.reminder_count == 0
    assert stale_contact.reminder_count == 1


def test_send_sign_request_stamps_first_notified_at(db: Session, monkeypatch) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "stamp-sender@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now)
    submitter = _submitter(db, submission=submission, user=_user(db, "stampee@pumasi.ai"))
    db.commit()

    _capture_sends(monkeypatch)
    notifications.send_sign_request(db, submitter, submission, SETTINGS)
    assert submitter.first_notified_at is not None
    first = submitter.first_notified_at

    # A later re-send (resend/reminder path) must not move the clock's origin.
    notifications.send_sign_request(db, submitter, submission, SETTINGS)
    assert submitter.first_notified_at == first


# --- document replaced ------------------------------------------------------


def test_on_document_replaced_emails_contacted_unsigned_signers_only(db: Session, monkeypatch) -> None:
    now = datetime.now(UTC)
    sender = _user(db, "doc-sender@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=now)

    _submitter(db, submission=submission, user=_user(db, "contacted-signer@pumasi.ai"), email_status="sent")
    _submitter(
        db,
        submission=submission,
        user=_user(db, "uncontacted@pumasi.ai"),
        order_index=1,
        email_status=None,
        role="Signer 2",
    )
    _submitter(db, submission=submission, user=_user(db, "cc-doc@pumasi.ai"), email_status="sent", is_cc=True, role="")
    db.commit()

    sent = _capture_sends(monkeypatch)
    notifications.on_document_replaced(db, submission, sender, SETTINGS)

    assert [m["to"] for m in sent] == [["contacted-signer@pumasi.ai"]]
    assert "replaced the document" in sent[0]["html"]
    assert "/sign/" in sent[0]["html"]
