"""Per-envelope reminder settings: the sender-chosen cadence drives the daily
sweep, the off switch silences it, and manual remind ignores both."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import notifications
from app.config import Settings

from .test_expiration import _me, _upload_template
from .test_notifications import _capture_sends, _submission, _submitter, _template, _user

SETTINGS = Settings(app_base_url="http://testserver")


def test_create_roundtrips_reminder_settings(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client)
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Custom cadence",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
            "reminders_enabled": False,
            "reminder_interval_days": 7,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reminders_enabled"] is False
    assert body["reminder_interval_days"] == 7


def test_create_defaults_reminders_on_every_3_days(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client)
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Defaults",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["reminders_enabled"] is True
    assert body["reminder_interval_days"] == 3


@pytest.mark.parametrize("interval", [0, 31])
def test_create_rejects_out_of_range_interval(
    admin_client: TestClient,
    user_client: TestClient,
    interval: int,
) -> None:
    template_id = _upload_template(admin_client)
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Bad interval",
            "signers": [{"role": "Signer 1", "user_id": _me(user_client)["id"]}],
            "reminder_interval_days": interval,
        },
    )
    assert resp.status_code == 422


def test_daily_sweep_uses_each_envelopes_interval(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    sends = _capture_sends(monkeypatch)
    sender = _user(db, "sender@pumasi.ai")
    fast_signer = _user(db, "fast@pumasi.ai")
    slow_signer = _user(db, "slow@pumasi.ai")
    template = _template(db, sender)
    two_days_ago = datetime.now(UTC) - timedelta(days=2)

    fast = _submission(db, sender=sender, template=template, created_at=two_days_ago)
    fast.reminder_interval_days = 1
    _submitter(db, submission=fast, user=fast_signer, email_status="sent")

    slow = _submission(db, sender=sender, template=template, created_at=two_days_ago)  # default: every 3 days
    _submitter(db, submission=slow, user=slow_signer, email_status="sent")
    db.commit()

    sent = notifications.run_daily_reminders(db, SETTINGS)
    db.commit()

    assert sent == 1
    recipients = {addr for call in sends for addr in call["to"]}
    assert recipients == {"fast@pumasi.ai"}


def test_daily_sweep_skips_disabled_envelopes_but_manual_remind_works(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sends = _capture_sends(monkeypatch)
    sender = _user(db, "sender@pumasi.ai")
    signer = _user(db, "signer@pumasi.ai")
    template = _template(db, sender)
    submission = _submission(db, sender=sender, template=template, created_at=datetime.now(UTC) - timedelta(days=10))
    submission.reminders_enabled = False
    _submitter(db, submission=submission, user=signer, email_status="sent")
    db.commit()

    assert notifications.run_daily_reminders(db, SETTINGS) == 0
    assert sends == []

    # The sender explicitly asking for a reminder overrides the off switch.
    assert notifications.send_reminders_for(db, submission, SETTINGS, min_days=0) == 1
    db.commit()
    recipients = {addr for call in sends for addr in call["to"]}
    assert recipients == {"signer@pumasi.ai"}
