"""Envelope expiration: create-time validation, the daily expire/warn sweeps,
and the signing-time rejection of past-due envelopes.

Sweep scenarios build rows directly via the ORM (same rationale as
test_notifications.py) so ``expires_at`` can be backdated.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.config import Settings
from app.models import AuditEvent, Submission, Submitter

from .test_notifications import _capture_sends, _submission, _submitter, _template, _user

SETTINGS = Settings(app_base_url="http://testserver")


def _upload_template(admin_client: TestClient, role: str = "Signer 1") -> int:
    fields = [
        {
            "id": "f1",
            "type": "signature",
            "role": role,
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        },
    ]
    resp = admin_client.post(
        "/api/templates",
        data={"name": "Doc"},
        files={"file": ("doc.pdf", _one_page_pdf(), "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["id"]
    resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields})
    assert resp.status_code == 200, resp.text
    return template_id


def _one_page_pdf() -> bytes:
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 700, "expiration test")
    c.save()
    return buf.getvalue()


def _me(client: TestClient) -> dict:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    return resp.json()


# --- create-time validation --------------------------------------------------


def test_create_with_future_expiry_roundtrips(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client)
    expires = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Expiring envelope",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
            "expires_at": expires,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["expires_at"] is not None


def test_create_without_expiry_defaults_to_none(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client)
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "No expiry",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["expires_at"] is None


def test_create_with_past_expiry_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client)
    expires = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Already over",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
            "expires_at": expires,
        },
    )
    assert resp.status_code == 422


# --- signing-time rejection --------------------------------------------------


def test_complete_on_past_due_envelope_is_409(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    template_id = _upload_template(admin_client)
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Soon overdue",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    submission_id = resp.json()["id"]
    submitter_id = resp.json()["submitters"][0]["id"]

    # Backdate the deadline: the envelope is now past due but not yet swept.
    db.execute(
        Submission.__table__.update()
        .where(Submission.id == submission_id)
        .values(expires_at=datetime.now(UTC) - timedelta(hours=1)),
    )
    db.commit()

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {}})
    assert resp.status_code == 409
    assert "expire" in resp.json()["detail"].lower()

    submitter_status = db.scalar(select(Submitter.status).where(Submitter.id == submitter_id))
    assert submitter_status in ("pending", "opened")


# --- the daily sweeps --------------------------------------------------------


def test_run_expirations_flips_past_due_and_notifies_contacted(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sends = _capture_sends(monkeypatch)
    sender = _user(db, "sender@pumasi.ai")
    signer = _user(db, "signer@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC) - timedelta(days=10))
    submission.expires_at = datetime.now(UTC) - timedelta(hours=2)
    _submitter(db, submission=submission, user=signer, email_status="sent")
    db.commit()

    expired = notifications.run_expirations(db, SETTINGS)
    db.commit()

    assert expired == 1
    db.refresh(submission)
    assert submission.status == "expired"
    events = db.scalars(select(AuditEvent).where(AuditEvent.submission_id == submission.id)).all()
    assert [e.event for e in events] == ["expired"]
    recipients = {addr for call in sends for addr in call["to"]}
    assert recipients == {"sender@pumasi.ai", "signer@pumasi.ai"}
    assert all("expire" in call["subject"].lower() for call in sends)


def test_run_expirations_skips_unexpired_and_non_pending(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sends = _capture_sends(monkeypatch)
    sender = _user(db, "sender@pumasi.ai")
    template = _template(db, sender)
    future = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC))
    future.expires_at = datetime.now(UTC) + timedelta(days=3)
    cancelled = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC), status="cancelled")
    cancelled.expires_at = datetime.now(UTC) - timedelta(days=3)
    no_expiry = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC))
    db.commit()

    assert notifications.run_expirations(db, SETTINGS) == 0
    db.commit()
    db.refresh(future)
    db.refresh(cancelled)
    db.refresh(no_expiry)
    assert future.status == "pending"
    assert cancelled.status == "cancelled"
    assert no_expiry.status == "pending"
    assert sends == []


def test_expiry_warning_sent_once_to_due_signers_and_sender(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sends = _capture_sends(monkeypatch)
    sender = _user(db, "sender@pumasi.ai")
    signer = _user(db, "signer@pumasi.ai")
    done = _user(db, "done@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC) - timedelta(days=5))
    submission.expires_at = datetime.now(UTC) + timedelta(days=1)
    _submitter(db, submission=submission, user=signer, email_status="sent")
    _submitter(db, submission=submission, user=done, status="completed", email_status="sent", role="Signer 2")
    db.commit()

    warned = notifications.send_expiry_warnings(db, SETTINGS)
    db.commit()

    assert warned == 1
    db.refresh(submission)
    assert submission.expiry_warned_at is not None
    recipients = {addr for call in sends for addr in call["to"]}
    # The completed signer has nothing left to do — only the pending signer
    # and the sender are warned.
    assert recipients == {"sender@pumasi.ai", "signer@pumasi.ai"}

    sends.clear()
    assert notifications.send_expiry_warnings(db, SETTINGS) == 0
    assert sends == []


def test_expiry_warning_not_sent_outside_window(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sends = _capture_sends(monkeypatch)
    sender = _user(db, "sender@pumasi.ai")
    signer = _user(db, "signer@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC))
    submission.expires_at = datetime.now(UTC) + timedelta(days=5)
    _submitter(db, submission=submission, user=signer, email_status="sent")
    db.commit()

    assert notifications.send_expiry_warnings(db, SETTINGS) == 0
    assert sends == []


def test_daily_job_reports_expiration_counts(make_client, tmp_path) -> None:
    client = make_client(Settings(job_token="test-job-token", data_dir=str(tmp_path), app_base_url="http://testserver"))
    resp = client.post("/api/jobs/daily", headers={"X-Job-Token": "test-job-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["expired"] == 0
    assert body["expiry_warnings"] == 0
