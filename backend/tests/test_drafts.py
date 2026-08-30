"""Draft envelopes: created silently, invisible to recipients, editable,
dispatched by /send, removable by DELETE."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.models import AuditEvent, Submission, Template

from .test_signing import (
    _create_submission,
    _field,
    _me_id,
    _submitter_id_for,
    _upload_template,
)


def _draft_submission(admin_client: TestClient, user_client: TestClient) -> dict:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Draft envelope",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
            "draft": True,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_draft_create_sends_no_email_and_no_sent_audit(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list = []
    monkeypatch.setattr(notifications.mailer, "send", lambda *a, **k: calls.append(a) or True)

    draft = _draft_submission(admin_client, user_client)
    assert draft["status"] == "draft"
    assert calls == []

    events = db.scalars(select(AuditEvent).where(AuditEvent.submission_id == draft["id"])).all()
    assert [e.event for e in events] == ["created"]
    assert all(s["email_status"] is None for s in draft["submitters"])


def test_draft_hidden_from_recipient_lists_and_sign_view(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    draft = _draft_submission(admin_client, user_client)
    submitter_id = _submitter_id_for(draft, _me_id(user_client))

    inbox = user_client.get("/api/submissions", params={"mine": "sign"})
    assert draft["id"] not in [s["id"] for s in inbox.json()]

    # The signing routes must not reveal an unsent envelope to its future
    # signer — not even as a 403.
    assert user_client.get(f"/api/sign/{submitter_id}").status_code == 404
    assert user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {}}).status_code == 404


def test_draft_visible_in_senders_sent_list(admin_client: TestClient, user_client: TestClient) -> None:
    draft = _draft_submission(admin_client, user_client)
    sent = admin_client.get("/api/submissions", params={"mine": "sent"})
    row = next(s for s in sent.json() if s["id"] == draft["id"])
    assert row["status"] == "draft"


def test_send_draft_flips_to_pending_emails_and_audits(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sends: list = []
    monkeypatch.setattr(notifications.mailer, "send", lambda settings, to, *a, **k: sends.append(to) or True)

    draft = _draft_submission(admin_client, user_client)
    resp = admin_client.post(f"/api/submissions/{draft['id']}/send")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["submitters"][0]["email_status"] == "sent"
    assert sends  # the sign request went out

    events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == draft["id"]).order_by(AuditEvent.id),
    ).all()
    assert [e.event for e in events] == ["created", "sent"]

    # Now that it's pending, signing works.
    submitter_id = _submitter_id_for(draft, _me_id(user_client))
    assert user_client.get(f"/api/sign/{submitter_id}").status_code == 200


def test_send_draft_revalidates_fields(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Fields emptied between save and send must 422, not dispatch an unsignable envelope."""
    draft = _draft_submission(admin_client, user_client)
    template_id = draft["template"]["id"]

    # Gut the template's fields after the draft was saved.
    resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [], "roles": []})
    assert resp.status_code == 200, resp.text

    send = admin_client.post(f"/api/submissions/{draft['id']}/send")

    assert send.status_code == 422
    assert send.json()["detail"]


def test_send_non_draft_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": _me_id(user_client)}])
    resp = admin_client.post(f"/api/submissions/{submission['id']}/send")
    assert resp.status_code == 409


def test_send_requires_sender_or_admin(admin_client: TestClient, user_client: TestClient) -> None:
    draft = _draft_submission(admin_client, user_client)
    resp = user_client.post(f"/api/submissions/{draft['id']}/send")
    assert resp.status_code == 403


def test_delete_draft_removes_rows_and_adhoc_files(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    draft = _draft_submission(admin_client, user_client)
    resp = admin_client.delete(f"/api/submissions/{draft['id']}")
    assert resp.status_code == 204, resp.text

    assert db.get(Submission, draft["id"]) is None
    assert db.scalars(select(AuditEvent).where(AuditEvent.submission_id == draft["id"])).all() == []
    # The template here isn't ad-hoc, so it must survive its draft's deletion.
    assert db.get(Template, draft["template"]["id"]) is not None

    assert admin_client.get(f"/api/submissions/{draft['id']}").status_code == 404


def test_delete_non_draft_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": _me_id(user_client)}])
    resp = admin_client.delete(f"/api/submissions/{submission['id']}")
    assert resp.status_code == 409


def test_draft_title_correction_allowed(admin_client: TestClient, user_client: TestClient) -> None:
    draft = _draft_submission(admin_client, user_client)
    resp = admin_client.patch(f"/api/submissions/{draft['id']}", json={"title": "Renamed draft"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Renamed draft"


def test_draft_signer_replacement_does_not_email(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sends: list = []
    monkeypatch.setattr(notifications.mailer, "send", lambda *a, **k: sends.append(a) or True)

    draft = _draft_submission(admin_client, user_client)
    other = make_client(app_settings)
    other.post("/api/auth/dev-login", json={"email": "other@pumasi.ai", "name": "Other"})
    other_id = _me_id(other)

    submitter_id = draft["submitters"][0]["id"]
    resp = admin_client.put(
        f"/api/submissions/{draft['id']}/submitters/{submitter_id}",
        json={"user_id": other_id},
    )
    assert resp.status_code == 200, resp.text
    assert sends == []
    assert resp.json()["submitters"][0]["email_status"] is None


def test_draft_hidden_from_recipient_by_direct_url(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """A would-be recipient must not read an unsent draft via any direct URL."""
    draft = _draft_submission(admin_client, user_client)
    template_id = draft["template"]["id"]

    assert user_client.get(f"/api/submissions/{draft['id']}").status_code == 403
    assert user_client.get(f"/api/submissions/{draft['id']}/events").status_code == 403
    assert user_client.get(f"/api/files/document-preview/{draft['id']}").status_code == 403
    assert user_client.get(f"/api/files/template-pdf/{template_id}").status_code == 403
    # Same for the signed-pdf/certificate artifacts — a listed submitter
    # must not be able to confirm the draft's existence via their
    # artifact-specific 404s either.
    assert user_client.get(f"/api/files/signed-pdf/{draft['id']}").status_code == 403
    assert user_client.get(f"/api/files/certificate/{draft['id']}").status_code == 403

    # The sender still sees everything.
    assert admin_client.get(f"/api/submissions/{draft['id']}").status_code == 200
    assert admin_client.get(f"/api/files/document-preview/{draft['id']}").status_code == 200

    # Once sent, the recipient regains access.
    assert admin_client.post(f"/api/submissions/{draft['id']}/send").status_code == 200
    assert user_client.get(f"/api/submissions/{draft['id']}").status_code == 200
    assert user_client.get(f"/api/files/document-preview/{draft['id']}").status_code == 200
