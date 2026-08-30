"""Tests for the submissions API and audit log.

``admin_client``/``user_client`` (from conftest) share one ``app_settings``
instance per test, so they hit the same test database and file storage —
letting a test create a template+submission as admin and then assert what a
plain user (as sender/submitter/bystander) can or can't do with it.
"""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notifications
from app.config import Settings
from app.models import AuditEvent, Submission, Submitter, User

FIXTURES = Path(__file__).parent / "fixtures"


def _upload_template(admin_client: TestClient, roles: list[str], *, name: str = "Doc") -> int:
    """Upload sample.pdf as admin and assign one signature field per role in ``roles``."""
    data = (FIXTURES / "sample.pdf").read_bytes()
    resp = admin_client.post(
        "/api/templates",
        data={"name": name},
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["id"]

    fields = [
        {
            "id": f"f{i}",
            "type": "signature",
            "role": role,
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        }
        for i, role in enumerate(roles)
    ]
    fields_resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields})
    assert fields_resp.status_code == 200, fields_resp.text
    return template_id


def _login(
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    email: str,
    name: str = "Signer",
) -> TestClient:
    client = make_client(app_settings)
    resp = client.post("/api/auth/dev-login", json={"email": email, "name": name})
    assert resp.status_code == 200, resp.text
    return client


def _me_id(client: TestClient) -> int:
    return client.get("/api/auth/me").json()["id"]


def _revoke_can_send(db: Session, client: TestClient) -> None:
    """Flip ``can_send`` to False for the logged-in user behind ``client``."""
    user = db.get(User, _me_id(client))
    user.can_send = False
    db.commit()


# --- create -------------------------------------------------------------


def test_create_with_cc_recipient_row(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    """A CC row needs no role, is stored as an is_cc submitter, and gets a
    copy notice at send time (order 0 = due immediately)."""
    cc_client = _login(make_client, app_settings, "cc-person@pumasi.ai", "CC Person")
    template_id = _upload_template(admin_client, ["Signer 1"])
    signer_id = _me_id(user_client)
    cc_id = _me_id(cc_client)

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "CC test",
            "signers": [
                {"role": "Signer 1", "user_id": signer_id},
                {"user_id": cc_id, "is_cc": True},
            ],
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    cc_row = next(s for s in body["submitters"] if s["user"]["id"] == cc_id)
    assert cc_row["is_cc"] is True
    assert cc_row["role"] == ""

    # The CC user sees the envelope in their list (Inbox = signer or CC),
    # flagged as a copy — the frontend never counts CC rows as action-needed.
    sign_list = cc_client.get("/api/submissions", params={"mine": "sign"})
    listed = next(item for item in sign_list.json() if item["id"] == body["id"])
    me_row = next(s for s in listed["submitters"] if s["user"]["id"] == cc_id)
    assert me_row["is_cc"] is True


def test_create_requires_at_least_one_signer(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    signer_id = _me_id(user_client)

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Only CC",
            "signers": [{"user_id": signer_id, "is_cc": True}],
        },
    )

    assert resp.status_code == 422


def test_create_stores_signing_order(admin_client: TestClient, user_client: TestClient, db: Session) -> None:
    template_id = _upload_template(admin_client, ["Signer 1", "Signer 2"])
    signer_id = _me_id(user_client)
    admin_id = _me_id(admin_client)

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Ordered",
            "signers": [
                {"role": "Signer 1", "user_id": signer_id, "order": 0},
                {"role": "Signer 2", "user_id": admin_id, "order": 1},
            ],
        },
    )

    assert resp.status_code == 201, resp.text
    by_role = {s["role"]: s for s in resp.json()["submitters"]}
    assert by_role["Signer 1"]["order_index"] == 0
    assert by_role["Signer 2"]["order_index"] == 1
    # Only the first group was asked to sign; the second signer's turn hasn't come.
    assert by_role["Signer 1"]["email_status"] is not None
    assert by_role["Signer 2"]["email_status"] is None


def test_label_fields_need_no_signer_role(admin_client: TestClient, user_client: TestClient) -> None:
    """A template with a role-less label field validates and sends fine —
    labels are sender text, not signable fields."""
    data = (FIXTURES / "sample.pdf").read_bytes()
    resp = admin_client.post(
        "/api/templates",
        data={"name": "With label"},
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )
    template_id = resp.json()["id"]
    fields = [
        {
            "id": "f0",
            "type": "signature",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "lbl",
            "type": "label",
            "role": "",
            "page": 0,
            "x": 0.1,
            "y": 0.3,
            "w": 0.5,
            "h": 0.04,
            "required": False,
            "default_value": "Static sender text",
        },
    ]
    fields_resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields})
    assert fields_resp.status_code == 200, fields_resp.text

    signer_id = _me_id(user_client)
    create = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Labelled",
            "signers": [{"role": "Signer 1", "user_id": signer_id}],
        },
    )
    assert create.status_code == 201, create.text


def test_create_submission_requires_sender(user_client: TestClient, db: Session) -> None:
    _revoke_can_send(db, user_client)

    resp = user_client.post(
        "/api/submissions",
        json={"template_id": 1, "title": "x", "signers": []},
    )
    assert resp.status_code == 403


def test_plain_pumasi_user_can_create_submission(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """A non-admin, non-revoked internal user (the default ``user_client``) can send.

    Uses their OWN template — templates are private per user, so sending
    from someone else's template is covered by the 403 test below.
    """
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])

    resp = user_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": admin_id}],
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["sender"]["email"] == "user@pumasi.ai"


def test_create_submission_success_writes_submitters_and_audit(
    admin_client: TestClient,
    user_client: TestClient,
    db,
) -> None:
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "message": "please sign",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Contract"
    assert body["message"] == "please sign"
    assert body["status"] == "pending"
    assert body["completed_at"] is None
    assert body["template"] == {"id": template_id, "name": "Doc", "is_adhoc": False}
    assert body["sender"] == {"id": admin_id, "name": "Admin", "email": "admin@pumasi.ai", "is_external": False}
    assert len(body["submitters"]) == 1
    submitter = body["submitters"][0]
    assert submitter["role"] == "Signer 1"
    assert submitter["status"] == "pending"
    assert submitter["signed_at"] is None
    assert submitter["user"]["id"] == user_id
    assert submitter["user"]["email"] == "user@pumasi.ai"
    assert submitter["user"]["is_external"] is False
    assert body["my_submitter_id"] is None  # admin (sender) isn't a submitter here

    submission_id = body["id"]
    submitters_in_db = db.scalars(select(Submitter).where(Submitter.submission_id == submission_id)).all()
    assert len(submitters_in_db) == 1
    assert submitters_in_db[0].user_id == user_id

    events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission_id).order_by(AuditEvent.id),
    ).all()
    assert [e.event for e in events] == ["created", "sent"]
    assert events[0].actor_user_id == admin_id
    assert events[1].detail == {"submitter_id": submitters_in_db[0].id}


def test_create_submission_response_includes_submitter_email_status(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """``SubmitterOut.email_status`` must be surfaced in the API response (not
    just the DB column) so the dashboard can show a delivery-failure
    indicator. ``app_settings`` leaves Graph mail config unset, so
    ``mailer.send`` short-circuits to ``False`` without any network call
    (see test_mailer.py) — email_status should reflect that failure.
    """
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["submitters"][0]["email_status"] == "failed"


def test_create_submission_sends_email_after_commit_visible_in_fresh_session(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: ``on_submission_created`` must run *after* the create
    transaction commits, not before — otherwise a slow/hung Graph send
    would hold the create request's transaction (and any row locks it
    implies) open for as long as the send takes, and a commit failure
    *after* sending would leave recipients with a working link to a
    submission that doesn't actually exist in the DB.

    Verified by checking, from inside the ``mailer.send`` monkeypatch,
    whether the submission is visible via ``db`` — a fixture-provided
    session distinct from the one the request itself used. Under Postgres's
    default READ COMMITTED isolation, a separate session can only see the
    row once its transaction has actually committed; if the email were
    still sent pre-commit (the bug this guards against), this lookup would
    come back empty.
    """
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    seen_committed: list[bool] = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        row = db.scalar(select(Submission).where(Submission.title == "Commit Order Test"))
        seen_committed.append(row is not None)
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Commit Order Test",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )

    assert resp.status_code == 201, resp.text
    assert seen_committed == [True]


def test_create_submission_missing_role_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1", "Signer 2"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_create_submission_extra_role_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [
                {"role": "Signer 1", "user_id": user_id},
                {"role": "Not On Template", "user_id": user_id},
            ],
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_create_submission_duplicate_role_mapping_is_422(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [
                {"role": "Signer 1", "user_id": user_id},
                {"role": "Signer 1", "user_id": admin_id},
            ],
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_create_submission_multiple_signers_creates_submitter_per_role(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Employee", "Manager"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [
                {"role": "Employee", "user_id": user_id},
                {"role": "Manager", "user_id": admin_id},
            ],
        },
    )

    assert resp.status_code == 201, resp.text
    submitters = resp.json()["submitters"]
    assert {(s["role"], s["user"]["id"]) for s in submitters} == {("Employee", user_id), ("Manager", admin_id)}


def test_create_submission_fieldless_role_must_still_be_mapped(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """A persisted role with no fields still counts: leaving it unmapped is a 422."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    fields_resp = admin_client.get(f"/api/templates/{template_id}")
    update = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": fields_resp.json()["fields"], "roles": ["Signer 1", "Witness"]},
    )
    assert update.status_code == 200, update.text

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )

    assert resp.status_code == 422
    assert "Witness" in resp.json()["detail"]


def test_create_submission_role_without_fields_is_422(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Mapping a signer to a role that has no fields is rejected with a clear message."""
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    fields_resp = admin_client.get(f"/api/templates/{template_id}")
    update = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": fields_resp.json()["fields"], "roles": ["Signer 1", "Witness"]},
    )
    assert update.status_code == 200, update.text

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [
                {"role": "Signer 1", "user_id": user_id},
                {"role": "Witness", "user_id": admin_id},
            ],
        },
    )

    assert resp.status_code == 422
    assert "no signable fields" in resp.json()["detail"]
    assert "Witness" in resp.json()["detail"]


def test_create_submission_unknown_user_is_422(admin_client: TestClient) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": 999999}],
        },
    )

    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_create_submission_template_not_found_is_404(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/submissions",
        json={"template_id": 999999, "title": "x", "signers": []},
    )
    assert resp.status_code == 404


def test_create_submission_archived_template_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    archive_resp = admin_client.post(f"/api/templates/{template_id}/archive")
    assert archive_resp.status_code == 200

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )

    assert resp.status_code == 409


# --- adhoc ----------------------------------------------------------------


def test_create_adhoc_submission_creates_template_and_submission(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    user_id = _me_id(user_client)
    data = (FIXTURES / "sample.pdf").read_bytes()

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "One-off NDA",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "Signer 1", "page": 0, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "One-off NDA"
    assert body["template"]["name"] == "One-off NDA"
    assert len(body["submitters"]) == 1
    assert body["submitters"][0]["user"]["id"] == user_id

    # the created template must not show up in the normal (non-adhoc) template list
    listing = admin_client.get("/api/templates").json()
    assert body["template"]["id"] not in [t["id"] for t in listing]


def test_create_adhoc_submission_accepts_optional_message(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    user_id = _me_id(user_client)
    data = (FIXTURES / "sample.pdf").read_bytes()

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "One-off with message",
            "message": "Please sign by Friday.",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "Signer 1", "page": 0, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["message"] == "Please sign by Friday."


def test_create_adhoc_submission_message_reaches_sign_request_email_body(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adhoc ``message`` form field must actually reach the "please
    sign" email body sent to the recipient (via ``notifications.
    on_submission_created`` -> ``_request_email_html``), not just round-trip
    through the JSON response."""
    user_id = _me_id(user_client)
    data = (FIXTURES / "sample.pdf").read_bytes()

    sent_bodies: list[str] = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        sent_bodies.append(html_body)
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "One-off with emailed message",
            "message": "Please sign by Friday, thanks!",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "Signer 1", "page": 0, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )

    assert resp.status_code == 201, resp.text
    assert len(sent_bodies) == 1
    assert "Please sign by Friday, thanks!" in sent_bodies[0]


def test_create_adhoc_submission_message_defaults_to_none(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    user_id = _me_id(user_client)
    data = (FIXTURES / "sample.pdf").read_bytes()

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "One-off without message",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "Signer 1", "page": 0, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["message"] is None


def test_create_adhoc_submission_page_out_of_range_cleans_up_storage(
    admin_client: TestClient,
    user_client: TestClient,
    app_settings: Settings,
) -> None:
    """Regression: a rejected field.page must not leave the just-converted tmp PDF on disk."""
    user_id = _me_id(user_client)
    data = (FIXTURES / "sample.pdf").read_bytes()  # sample.pdf has 2 pages: 0 and 1 are valid

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "Bad Page NDA",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "Signer 1", "page": 99, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )

    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]

    data_dir = Path(app_settings.data_dir)
    leftover_files = [p for p in data_dir.rglob("*") if p.is_file()]
    assert leftover_files == []

    # and no template row should have survived either
    listing = admin_client.get("/api/templates").json()
    assert listing == []


# --- POST /api/submissions/adhoc/merged-document ------------------------------


def _one_page_pdf(marker: str) -> bytes:
    """A single-page PDF whose extracted text contains ``marker``."""
    import io

    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(400, 300))
    c.drawString(50, 150, marker)
    c.save()
    return buf.getvalue()


def test_adhoc_merged_document_merges_pdfs_in_upload_order(admin_client: TestClient) -> None:
    import io

    from pypdf import PdfReader

    resp = admin_client.post(
        "/api/submissions/adhoc/merged-document",
        files=[
            ("files", ("first.pdf", _one_page_pdf("doc-one"), "application/pdf")),
            ("files", ("second.pdf", _one_page_pdf("doc-two"), "application/pdf")),
        ],
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(resp.content))
    assert len(reader.pages) == 2
    assert "doc-one" in reader.pages[0].extract_text()
    assert "doc-two" in reader.pages[1].extract_text()


def test_adhoc_merged_document_requires_sender(user_client: TestClient, db: Session) -> None:
    _revoke_can_send(db, user_client)

    resp = user_client.post(
        "/api/submissions/adhoc/merged-document",
        files=[("files", ("a.pdf", _one_page_pdf("x"), "application/pdf"))],
    )
    assert resp.status_code == 403


def test_adhoc_merged_document_unsupported_extension_is_422(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/submissions/adhoc/merged-document",
        files=[
            ("files", ("a.pdf", _one_page_pdf("x"), "application/pdf")),
            ("files", ("notes.exe", b"MZ binary", "application/octet-stream")),
        ],
    )
    assert resp.status_code == 422
    assert "notes.exe" in resp.json()["detail"]


def test_adhoc_merged_document_no_files_is_422(admin_client: TestClient) -> None:
    resp = admin_client.post("/api/submissions/adhoc/merged-document")
    assert resp.status_code == 422


def test_create_adhoc_submission_requires_sender(user_client: TestClient, db: Session) -> None:
    _revoke_can_send(db, user_client)

    resp = user_client.post(
        "/api/submissions/adhoc",
        data={"title": "x", "signers_json": "[]", "fields_json": "[]"},
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 403


def test_create_adhoc_submission_bad_signers_json_is_422(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={"title": "x", "signers_json": "not json", "fields_json": "[]"},
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 422


# --- copy ---------------------------------------------------------------


def _adhoc_submission(admin_client: TestClient, user_id: int, *, title: str = "One-off doc") -> dict:
    """Create an ad-hoc (throwaway-template) submission and return its SubmissionOut body."""
    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": title,
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "Signer 1", "page": 0, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_copy_envelope_creates_draft_copy(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    user_id = _me_id(user_client)
    future = "2030-01-02T00:00:00+00:00"
    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Original title",
            "message": "Original message",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
            "expires_at": future,
            "reminders_enabled": False,
            "reminder_interval_days": 7,
        },
    ).json()

    resp = admin_client.post(f"/api/submissions/{created['id']}/copy")

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] != created["id"]
    assert body["status"] == "draft"
    assert body["title"] == "Original title"
    assert body["message"] == "Original message"
    assert body["reminders_enabled"] is False
    assert body["reminder_interval_days"] == 7
    assert body["expires_at"] is not None
    # Every copy is standalone: even reusable templates are cloned into ad-hoc drafts.
    assert body["template"]["id"] != template_id
    [copy_signer] = body["submitters"]
    assert copy_signer["user"]["id"] == user_id
    assert copy_signer["role"] == "Signer 1"
    assert copy_signer["status"] == "pending"

    # Source stays untouched, and the copy's audit trail records provenance.
    assert admin_client.get(f"/api/submissions/{created['id']}").json()["status"] == "pending"
    event = db.execute(
        select(AuditEvent).where(AuditEvent.submission_id == body["id"], AuditEvent.event == "created"),
    ).scalar_one()
    assert event.detail["copied_from_submission_id"] == created["id"]


def test_copy_of_template_envelope_is_standalone(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """Copies detach from reusable templates so editing them can't touch the original."""
    from app.models import Template

    template_id = _upload_template(admin_client, ["Signer 1"])
    # Snapshot the source template before copy operations
    source = db.get(Template, template_id)
    source_fields = source.fields
    source_pdf_key = source.pdf_key

    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "From template",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    ).json()

    body = admin_client.post(f"/api/submissions/{created['id']}/copy").json()

    assert body["template"]["id"] != template_id
    clone = db.get(Template, body["template"]["id"])
    assert clone.is_adhoc is True
    assert clone.fields == source_fields
    assert clone.pdf_key != source_pdf_key


def test_copy_preserves_order_and_cc(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings: Settings,
) -> None:
    cc_client = _login(make_client, app_settings, "dup-cc@pumasi.ai", "Dup CC")
    template_id = _upload_template(admin_client, ["Signer 1"])
    user_id = _me_id(user_client)
    cc_id = _me_id(cc_client)
    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Ordered",
            "signers": [
                {"role": "Signer 1", "user_id": user_id, "order": 1},
                {"user_id": cc_id, "is_cc": True, "order": 0},
            ],
        },
    ).json()

    body = admin_client.post(f"/api/submissions/{created['id']}/copy").json()

    by_user = {s["user"]["id"]: s for s in body["submitters"]}
    assert by_user[user_id]["order_index"] == 1
    assert by_user[cc_id]["is_cc"] is True
    assert by_user[cc_id]["order_index"] == 0


def test_copy_completed_envelope_allowed(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Done deal",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    ).json()
    db.get(Submission, created["id"]).status = "completed"
    db.commit()

    resp = admin_client.post(f"/api/submissions/{created['id']}/copy")

    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "draft"


def test_copy_drops_past_expiry(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    from datetime import UTC, datetime

    template_id = _upload_template(admin_client, ["Signer 1"])
    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Expired source",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    ).json()
    db.get(Submission, created["id"]).expires_at = datetime(2020, 1, 1, tzinfo=UTC)
    db.commit()

    body = admin_client.post(f"/api/submissions/{created['id']}/copy").json()

    assert body["expires_at"] is None


def test_copy_forbidden_for_non_sender(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Being a signer on the envelope grants no right to copy it."""
    template_id = _upload_template(admin_client, ["Signer 1"])
    created = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Not yours",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    ).json()

    resp = user_client.post(f"/api/submissions/{created['id']}/copy")

    assert resp.status_code == 403


def test_copy_requires_can_send(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    template_id = _upload_template(user_client, ["Signer 1"])
    created = user_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Mine but revoked",
            "signers": [{"role": "Signer 1", "user_id": _me_id(admin_client)}],
        },
    ).json()
    _revoke_can_send(db, user_client)

    resp = user_client.post(f"/api/submissions/{created['id']}/copy")

    assert resp.status_code == 403


def test_copy_adhoc_deep_copies_template_files(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    """Deleting the copied draft must never destroy the source envelope's files."""
    from app.models import Template
    from app.storage import get_storage

    source = _adhoc_submission(admin_client, _me_id(user_client))

    body = admin_client.post(f"/api/submissions/{source['id']}/copy").json()

    copy_template_id = body["template"]["id"]
    assert copy_template_id != source["template"]["id"]
    source_template = db.get(Template, source["template"]["id"])
    copy_template = db.get(Template, copy_template_id)
    assert copy_template.is_adhoc is True
    assert copy_template.fields == source_template.fields
    assert copy_template.pdf_key != source_template.pdf_key

    # Deleting the copied draft removes only the copy's files.
    delete = admin_client.delete(f"/api/submissions/{body['id']}")
    assert delete.status_code == 204, delete.text
    storage = get_storage(app_settings)
    assert storage.exists(source_template.pdf_key)
    assert storage.exists(source_template.original_file_key)


def test_copy_carries_entered_values_as_prefills(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """DocuSign-style: text/dropdown/radio/checkbox survive the copy as prefills;
    signature/date/name (auto-filled or non-copyable) do not."""
    from app.models import Submitter, Template

    user_id = _me_id(user_client)
    fields = [
        {
            "id": "sig",
            "type": "signature",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "txt",
            "type": "text",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.2,
            "w": 0.2,
            "h": 0.05,
            "required": False,
        },
        {
            "id": "dd",
            "type": "dropdown",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.3,
            "w": 0.2,
            "h": 0.05,
            "required": False,
            "options": ["A", "B"],
        },
        {
            "id": "cb",
            "type": "checkbox",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.4,
            "w": 0.05,
            "h": 0.05,
            "required": False,
        },
        {
            "id": "dt",
            "type": "date",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.5,
            "w": 0.2,
            "h": 0.05,
            "required": False,
        },
    ]
    import json

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "Values source",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": json.dumps(fields),
        },
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    source = resp.json()
    # Simulate the signer having filled things in.
    submitter = db.get(Submitter, source["submitters"][0]["id"])
    submitter.values = {"sig": "sig-1", "txt": "hello world", "dd": "B", "cb": True, "dt": "2026-08-23"}
    db.commit()

    body = admin_client.post(f"/api/submissions/{source['id']}/copy").json()

    copied = {f["id"]: f for f in db.get(Template, body["template"]["id"]).fields}
    assert copied["txt"]["default_value"] == "hello world"
    assert copied["dd"]["default_value"] == "B"
    assert copied["cb"]["default_value"] == "true"
    assert copied["sig"].get("default_value") in (None, "")
    assert copied["dt"].get("default_value") in (None, "")


def test_copy_ignores_invalid_or_foreign_values(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """A dropdown value not among the options, and values belonging to a
    different role's submitter, are not copied."""
    from app.models import Submitter, Template

    user_id = _me_id(user_client)
    fields = [
        {
            "id": "dd",
            "type": "dropdown",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.3,
            "w": 0.2,
            "h": 0.05,
            "required": False,
            "options": ["A", "B"],
        },
    ]
    import json

    source = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "Bad values source",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": json.dumps(fields),
        },
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    ).json()
    submitter = db.get(Submitter, source["submitters"][0]["id"])
    submitter.values = {"dd": "Z"}  # not an option
    db.commit()

    body = admin_client.post(f"/api/submissions/{source['id']}/copy").json()

    copied = {f["id"]: f for f in db.get(Template, body["template"]["id"]).fields}
    assert copied["dd"].get("default_value") in (None, "")


def test_copy_clears_stale_prefill_when_signer_cleared_value(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """A field already carrying a ``default_value`` prefill (e.g. from an
    earlier Copy) must not survive into a new copy once the signer's
    recorded value for it says otherwise — an unchecked checkbox or blanked
    text field must not resurrect a stale prefill."""
    from app.models import Submitter, Template

    user_id = _me_id(user_client)
    fields = [
        {
            "id": "txt",
            "type": "text",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.2,
            "w": 0.2,
            "h": 0.05,
            "required": False,
            "default_value": "stale text",
        },
        {
            "id": "cb",
            "type": "checkbox",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.4,
            "w": 0.05,
            "h": 0.05,
            "required": False,
            "default_value": "true",
        },
    ]
    import json

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "Stale prefill source",
            "signers_json": f'[{{"role": "Signer 1", "user_id": {user_id}}}]',
            "fields_json": json.dumps(fields),
        },
        files={"file": ("sample.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    source = resp.json()
    # The signer unchecked the box and cleared the text — the field still
    # carries its old default_value, but ``values`` now records the final,
    # cleared state.
    submitter = db.get(Submitter, source["submitters"][0]["id"])
    submitter.values = {"txt": "", "cb": False}
    db.commit()

    body = admin_client.post(f"/api/submissions/{source['id']}/copy").json()

    copied = {f["id"]: f for f in db.get(Template, body["template"]["id"]).fields}
    assert copied["txt"].get("default_value") in (None, "")
    assert copied["cb"].get("default_value") in (None, "")


# --- list: mine=sign / mine=sent -------------------------------------------


def test_create_adhoc_submission_signer_without_fields_is_422(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """An ad-hoc signer whose role has no fields is rejected server-side, matching the compose UI's client-side rule."""
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    data = (FIXTURES / "sample.pdf").read_bytes()

    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "One-off",
            "signers_json": (
                f'[{{"role": "signer-1", "user_id": {user_id}}}, {{"role": "signer-2", "user_id": {admin_id}}}]'
            ),
            "fields_json": (
                '[{"id": "f1", "type": "signature", "role": "signer-1", "page": 0, '
                '"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "required": true}]'
            ),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )

    assert resp.status_code == 422
    assert "no signable fields" in resp.json()["detail"]
    assert "signer-2" in resp.json()["detail"]


def test_list_requires_mine_param(admin_client: TestClient) -> None:
    resp = admin_client.get("/api/submissions")
    assert resp.status_code == 422


def test_list_mine_sign_lists_for_signer_not_others(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    user_id = _me_id(user_client)
    bystander = _login(make_client, app_settings, "bystander@pumasi.ai")
    template_id = _upload_template(admin_client, ["Signer 1"])
    create_resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )
    submission_id = create_resp.json()["id"]
    submitter_id = create_resp.json()["submitters"][0]["id"]

    signer_listing = user_client.get("/api/submissions", params={"mine": "sign"}).json()
    assert [s["id"] for s in signer_listing] == [submission_id]
    assert signer_listing[0]["my_submitter_id"] == submitter_id

    bystander_listing = bystander.get("/api/submissions", params={"mine": "sign"}).json()
    assert bystander_listing == []


def test_list_mine_sign_includes_cancelled(admin_client: TestClient, user_client: TestClient) -> None:
    """Voided envelopes stay visible to recipients (with their Voided status)
    instead of silently vanishing — review fix, reverses the old exclusion."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    create_resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )
    submission_id = create_resp.json()["id"]
    cancel_resp = admin_client.post(f"/api/submissions/{submission_id}/cancel")
    assert cancel_resp.status_code == 200

    signer_listing = user_client.get("/api/submissions", params={"mine": "sign"}).json()
    assert [s["id"] for s in signer_listing] == [submission_id]
    assert signer_listing[0]["status"] == "cancelled"


def test_list_mine_sent_allows_plain_sender(admin_client: TestClient, user_client: TestClient) -> None:
    """A plain (non-admin) sender's own mine=sent listing includes what they created.

    Regression test: DashboardView fetches ``mine=sent`` for every
    ``can_send`` user (not just admins), so the route must not admin-gate a
    query that already scopes to ``created_by == user.id``.
    """
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    create_resp = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Mine", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    )
    assert create_resp.status_code == 201, create_resp.text
    submission_id = create_resp.json()["id"]

    listing = user_client.get("/api/submissions", params={"mine": "sent"})
    assert listing.status_code == 200, listing.text
    assert [s["id"] for s in listing.json()] == [submission_id]


def test_list_mine_sent_excludes_other_senders(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    admin_id = _me_id(admin_client)
    other_sender = _login(make_client, app_settings, "other-sender@pumasi.ai")
    template_id = _upload_template(user_client, ["Signer 1"])
    create_resp = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Mine", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    )
    assert create_resp.status_code == 201, create_resp.text

    listing = other_sender.get("/api/submissions", params={"mine": "sent"})
    assert listing.status_code == 200, listing.text
    assert listing.json() == []


def test_list_mine_sent_newest_first_with_submitters(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    first = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "First", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()
    second = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Second", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()

    listing = admin_client.get("/api/submissions", params={"mine": "sent"}).json()
    assert [s["id"] for s in listing] == [second["id"], first["id"]]
    assert len(listing[0]["submitters"]) == 1


# --- get single -------------------------------------------------------------


def test_get_submission_sender_and_submitter_can_view(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    assert admin_client.get(f"/api/submissions/{submission_id}").status_code == 200
    assert user_client.get(f"/api/submissions/{submission_id}").status_code == 200


def test_get_submission_forbidden_for_unrelated_user(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    user_id = _me_id(user_client)
    bystander = _login(make_client, app_settings, "bystander2@pumasi.ai")
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = bystander.get(f"/api/submissions/{submission_id}")
    assert resp.status_code == 403


def test_get_submission_not_found_is_404(admin_client: TestClient) -> None:
    resp = admin_client.get("/api/submissions/999999")
    assert resp.status_code == 404


# --- cancel -------------------------------------------------------------


def test_cancel_by_sender_flips_status(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.post(f"/api/submissions/{submission_id}/cancel")

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    assert admin_client.get(f"/api/submissions/{submission_id}").json()["status"] == "cancelled"


def test_cancel_writes_audit_event(admin_client: TestClient, user_client: TestClient, db) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    admin_client.post(f"/api/submissions/{submission_id}/cancel")

    events = db.scalars(
        select(AuditEvent.event).where(AuditEvent.submission_id == submission_id).order_by(AuditEvent.id),
    ).all()
    assert events == ["created", "sent", "cancelled"]


def test_cancel_by_unrelated_user_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    user_id = _me_id(user_client)
    bystander = _login(make_client, app_settings, "bystander3@pumasi.ai")
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = bystander.post(f"/api/submissions/{submission_id}/cancel")
    assert resp.status_code == 403


def test_cancel_on_completed_submission_is_409(admin_client: TestClient, user_client: TestClient, db) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    submission = db.get(Submission, submission_id)
    submission.status = "completed"
    db.commit()

    resp = admin_client.post(f"/api/submissions/{submission_id}/cancel")
    assert resp.status_code == 409


def test_cancel_on_cancelled_submission_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]
    admin_client.post(f"/api/submissions/{submission_id}/cancel")

    resp = admin_client.post(f"/api/submissions/{submission_id}/cancel")
    assert resp.status_code == 409


# --- correct (PATCH title/message) --------------------------------------


def test_correct_by_creator_updates_title_and_message(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"title": "Contract v2", "message": "Please review the updated terms"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Contract v2"
    assert body["message"] == "Please review the updated terms"


def test_correct_writes_audit_event(admin_client: TestClient, user_client: TestClient, db) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": "Contract v2"})
    assert resp.status_code == 200, resp.text

    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    assert [e["event"] for e in events] == ["created", "sent", "corrected"]
    assert events[-1]["detail"]["changed"] == ["title"]


def test_correct_by_non_creator_non_admin_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    # user_client (non-admin) is the sender/creator here; admin_client is the signer.
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    submission_id = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    ).json()["id"]

    bystander = _login(make_client, app_settings, "bystander-correct@pumasi.ai")
    resp = bystander.patch(f"/api/submissions/{submission_id}", json={"title": "Hijacked"})
    assert resp.status_code == 403


def test_correct_by_admin_non_creator_is_200(admin_client: TestClient, user_client: TestClient) -> None:
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    submission_id = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": "Reviewed by admin"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Reviewed by admin"


def test_correct_on_completed_submission_is_409(admin_client: TestClient, user_client: TestClient, db) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    submission = db.get(Submission, submission_id)
    submission.status = "completed"
    db.commit()

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": "Too late"})
    assert resp.status_code == 409


def test_correct_with_empty_title_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": "   "})
    assert resp.status_code == 422


def test_correct_with_title_too_long_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": "x" * 256})
    assert resp.status_code == 422


def test_correct_with_no_fields_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={})
    assert resp.status_code == 422


def test_correct_explicit_null_message_clears_it(admin_client: TestClient, user_client: TestClient) -> None:
    """PATCH {"message": null} means "clear the message" — distinct from omitting it."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "message": "Please sign by Friday",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"message": None})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["message"] is None
    assert body["title"] == "Contract"


def test_correct_absent_message_is_untouched(admin_client: TestClient, user_client: TestClient) -> None:
    """PATCH {"title": ...} without "message" at all must leave the existing message alone."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "message": "Please sign by Friday",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": "Contract v2"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Contract v2"
    assert body["message"] == "Please sign by Friday"


def test_correct_explicit_null_title_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    """Title stays non-nullable — an explicit null (unlike an absent key) is rejected."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": None})
    assert resp.status_code == 422


def test_correct_explicit_null_title_alongside_message_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    """Even with a valid ``message`` alongside it, an explicit null title must still 422 (not be silently skipped)."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"title": None, "message": "hi"})
    assert resp.status_code == 422

    unchanged = admin_client.get(f"/api/submissions/{submission_id}").json()
    assert unchanged["title"] == "Contract"


def test_correct_changed_list_excludes_unchanged_message(admin_client: TestClient, user_client: TestClient) -> None:
    """The audit ``changed`` list must reflect real diffs, not just which keys the client sent."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "message": "Please sign by Friday",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    ).json()["id"]

    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"title": "Contract v2", "message": "Please sign by Friday"},
    )
    assert resp.status_code == 200, resp.text

    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    assert events[-1]["event"] == "corrected"
    assert events[-1]["detail"]["changed"] == ["title"]


def test_correct_noop_patch_writes_no_audit_event(admin_client: TestClient, user_client: TestClient) -> None:
    """A PATCH that changes nothing (same title/message as already stored) must not append a corrected event."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "message": "Please sign by Friday",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    ).json()["id"]

    before_events = admin_client.get(f"/api/submissions/{submission_id}/events").json()

    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"title": "Contract", "message": "Please sign by Friday"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Contract"
    assert resp.json()["message"] == "Please sign by Friday"

    after_events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    assert after_events == before_events
    assert [e["event"] for e in after_events] == ["created", "sent"]


# --- remind -------------------------------------------------------------


def test_remind_by_sender_ok_when_pending(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.post(f"/api/submissions/{submission_id}/remind")
    assert resp.status_code == 200


def test_remind_by_non_sender_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = user_client.post(f"/api/submissions/{submission_id}/remind")
    assert resp.status_code == 403


def test_remind_by_admin_non_sender_ok(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Admins can remind on any pending envelope, like every other management
    action (cancel/correct/replace all already admit admins)."""
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    submission_id = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    ).json()["id"]

    resp = admin_client.post(f"/api/submissions/{submission_id}/remind")
    assert resp.status_code == 200


def test_remind_when_not_pending_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]
    admin_client.post(f"/api/submissions/{submission_id}/cancel")

    resp = admin_client.post(f"/api/submissions/{submission_id}/remind")
    assert resp.status_code == 409


# --- audit module -----------------------------------------------------------


def test_audit_record_does_not_commit(admin_client: TestClient, user_client: TestClient, db) -> None:
    """audit.record flushes but never commits — a caller rollback removes its rows too."""
    from app import audit

    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    before = db.scalar(select(AuditEvent.id).order_by(AuditEvent.id.desc()))

    session = db
    audit.record(session, submission_id, "opened", actor_user_id=user_id)
    session.rollback()

    after_ids = set(db.scalars(select(AuditEvent.id)))
    assert before in after_ids or before is None
    # the just-recorded "opened" event must not have survived the rollback
    opened_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission_id, AuditEvent.event == "opened"),
    ).all()
    assert opened_events == []


# --- events timeline --------------------------------------------------------


def test_events_sender_sees_created_and_sent(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.get(f"/api/submissions/{submission_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert [e["event"] for e in events] == ["created", "sent"]
    # actor is the sending admin; detail carries the submitter id for "sent"
    admin_email = admin_client.get("/api/auth/me").json()["email"]
    assert events[0]["actor"]["email"] == admin_email
    assert "submitter_id" in events[1]["detail"]
    # signer IPs are not part of the payload
    assert all("ip_address" not in e for e in events)


def test_events_visible_to_submitter_but_not_unrelated_user(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    """DocuSign-style: every party to the envelope (sender or signer) can see
    its history; anyone else still can't."""
    user_id = _me_id(user_client)
    bystander = _login(make_client, app_settings, "bystander3@pumasi.ai")
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    submitter_resp = user_client.get(f"/api/submissions/{submission_id}/events")
    assert submitter_resp.status_code == 200
    assert [e["event"] for e in submitter_resp.json()] == ["created", "sent"]

    assert bystander.get(f"/api/submissions/{submission_id}/events").status_code == 403


def test_events_not_found_is_404(admin_client: TestClient) -> None:
    assert admin_client.get("/api/submissions/999999/events").status_code == 404


def test_submitter_out_includes_reminder_fields(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    submitter = admin_client.get(f"/api/submissions/{submission_id}").json()["submitters"][0]
    assert submitter["reminder_count"] == 0
    assert submitter["last_reminded_at"] is None

    assert admin_client.post(f"/api/submissions/{submission_id}/remind").status_code == 200
    submitter = admin_client.get(f"/api/submissions/{submission_id}").json()["submitters"][0]
    assert submitter["reminder_count"] == 1
    assert submitter["last_reminded_at"] is not None


# --- public_uid ---------------------------------------------------------


def test_submission_gets_random_public_uid(
    admin_client: TestClient,
    user_client: TestClient,
    db,
) -> None:
    """public_uid is generated on insert: 32 lowercase hex chars (uuid4), unique per row."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    ids = []
    for title in ("One", "Two"):
        resp = admin_client.post(
            "/api/submissions",
            json={
                "template_id": template_id,
                "title": title,
                "signers": [{"role": "Signer 1", "user_id": user_id}],
            },
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])

    first, second = (db.get(Submission, submission_id) for submission_id in ids)
    assert re.fullmatch(r"[0-9a-f]{32}", first.public_uid)
    assert re.fullmatch(r"[0-9a-f]{32}", second.public_uid)
    assert first.public_uid != second.public_uid


# --- replace signer (PUT .../submitters/{id}) -------------------------------


def test_replace_signer_internal_swaps_user_resets_fields_and_writes_audit(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
    db,
) -> None:
    old_user_id = _me_id(user_client)
    old_email = user_client.get("/api/auth/me").json()["email"]
    new_signer = _login(make_client, app_settings, "newsigner@pumasi.ai", "New Signer")
    new_user_id = _me_id(new_signer)
    template_id = _upload_template(admin_client, ["Signer 1"])
    create_resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": old_user_id}],
        },
    )
    submission_id = create_resp.json()["id"]
    submitter_id = create_resp.json()["submitters"][0]["id"]

    # Bump reminder bookkeeping first so the reset is actually observable.
    assert admin_client.post(f"/api/submissions/{submission_id}/remind").status_code == 200

    resp = admin_client.put(
        f"/api/submissions/{submission_id}/submitters/{submitter_id}",
        json={"user_id": new_user_id},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    submitter_out = next(s for s in body["submitters"] if s["id"] == submitter_id)
    assert submitter_out["user"]["id"] == new_user_id
    assert submitter_out["status"] == "pending"
    assert submitter_out["signed_at"] is None
    assert submitter_out["last_reminded_at"] is None
    assert submitter_out["reminder_count"] == 0

    row = db.get(Submitter, submitter_id)
    assert row.user_id == new_user_id
    assert row.values == {}
    assert row.ip_address is None
    assert row.access_uid is None

    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    corrected = next(e for e in events if e["event"] == "corrected")
    assert corrected["detail"]["submitter_id"] == submitter_id
    assert corrected["detail"]["from"] == {"user_id": old_user_id, "email": old_email}
    assert corrected["detail"]["to"] == {"user_id": new_user_id, "email": "newsigner@pumasi.ai"}


def test_replace_signer_by_non_creator_non_admin_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    submission = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    ).json()
    submitter_id = submission["submitters"][0]["id"]

    bystander = _login(make_client, app_settings, "bystander-replace@pumasi.ai")
    resp = bystander.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": admin_id},
    )
    assert resp.status_code == 403


def test_replace_signer_by_admin_non_creator_is_200(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    admin_id = _me_id(admin_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    submission = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    ).json()
    submitter_id = submission["submitters"][0]["id"]
    other = _login(make_client, app_settings, "other-replace@pumasi.ai")
    other_id = _me_id(other)

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": other_id},
    )
    assert resp.status_code == 200, resp.text


def test_replace_signer_when_not_pending_is_409(admin_client: TestClient, user_client: TestClient, db) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()
    submitter_id = submission["submitters"][0]["id"]

    submission_row = db.get(Submission, submission["id"])
    submission_row.status = "cancelled"
    db.commit()

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": user_id},
    )
    assert resp.status_code == 409


def test_replace_signer_target_not_found_is_404(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()["id"]

    resp = admin_client.put(
        f"/api/submissions/{submission_id}/submitters/999999",
        json={"user_id": user_id},
    )
    assert resp.status_code == 404


def test_replace_signer_completed_target_is_409(admin_client: TestClient, user_client: TestClient, db) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()
    submitter_id = submission["submitters"][0]["id"]

    submitter_row = db.get(Submitter, submitter_id)
    submitter_row.status = "completed"
    db.commit()

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": user_id},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Signer already signed"


def test_replace_signer_new_user_not_found_is_404(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Contract", "signers": [{"role": "Signer 1", "user_id": user_id}]},
    ).json()
    submitter_id = submission["submitters"][0]["id"]

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": 999999},
    )
    assert resp.status_code == 404


def test_replace_signer_duplicate_user_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Employee", "Manager"])
    submission = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [
                {"role": "Employee", "user_id": user_id},
                {"role": "Manager", "user_id": admin_id},
            ],
        },
    ).json()
    employee_submitter_id = next(s["id"] for s in submission["submitters"] if s["role"] == "Employee")

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{employee_submitter_id}",
        json={"user_id": admin_id},
    )
    assert resp.status_code == 409


def test_replace_signer_to_external_gets_fresh_access_uid_and_old_link_404s(
    admin_client: TestClient,
    user_client: TestClient,
    db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_external_signing import _capture_mail, _provision_external

    sent = _capture_mail(monkeypatch)
    old_user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])
    submission = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Contract",
            "signers": [{"role": "Signer 1", "user_id": old_user_id}],
        },
    ).json()
    submitter_id = submission["submitters"][0]["id"]

    ext_id = _provision_external(admin_client, email="newext@vendor.com", name="New Ext")

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": ext_id},
    )
    assert resp.status_code == 200, resp.text

    row = db.get(Submitter, submitter_id)
    assert row.access_uid is not None

    # a sign-request email went out to the new external signer with a fresh token link
    request_mails = [m for m in sent if "requests your signature" in m["subject"]]
    assert any(row.access_uid in m["body"] and "newext@vendor.com" in m["to"] for m in request_mails)

    # the internal /sign/{submitter_id} link (used while the old internal
    # user held this submitter) is meaningless now, but the old access_uid
    # never existed for this submitter, so what really matters is that the
    # *current* access_uid resolves and nothing else does.
    other_uid_resp = admin_client.get("/api/sign/token/" + ("0" * 32))
    assert other_uid_resp.status_code == 404
    assert admin_client.get(f"/api/sign/token/{row.access_uid}").status_code == 200


def test_replace_external_signer_kills_old_access_uid(
    admin_client: TestClient,
    db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_external_signing import _capture_mail, _external_submission

    _capture_mail(monkeypatch)
    submission, old_access_uid, submitter_id = _external_submission(admin_client, db)

    resp = admin_client.post("/api/users", json={"email": "replacement@pumasi.ai", "name": "Replacement"})
    new_user_id = resp.json()["id"]

    resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": new_user_id},
    )
    assert resp.status_code == 200, resp.text

    # the old external link must no longer resolve
    assert admin_client.get(f"/api/sign/token/{old_access_uid}").status_code == 404

    row = db.get(Submitter, submitter_id)
    assert row.access_uid is None  # replacement user is internal
    assert row.access_uid != old_access_uid


def test_submission_response_includes_public_uid(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """API responses expose the random public_uid so the stamped ID can be looked up."""
    user_id = _me_id(user_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "UID exposure",
            "signers": [{"role": "Signer 1", "user_id": user_id}],
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert re.fullmatch(r"[0-9a-f]{32}", created["public_uid"])

    fetched = admin_client.get(f"/api/submissions/{created['id']}").json()
    assert fetched["public_uid"] == created["public_uid"]


def test_create_submission_from_another_users_template_is_403(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Templates are private: a sender cannot send from another user's template."""
    admin_id = _me_id(admin_client)
    template_id = _upload_template(admin_client, ["Signer 1"])

    resp = user_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Not yours",
            "signers": [{"role": "Signer 1", "user_id": admin_id}],
        },
    )

    assert resp.status_code == 403


# --- per-user archive ----------------------------------------------------


def _simple_submission(admin_client: TestClient, user_client: TestClient, title: str = "Archive test") -> int:
    template_id = _upload_template(admin_client, ["Signer 1"])
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": title,
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_archive_hides_for_me_only(admin_client: TestClient, user_client: TestClient) -> None:
    submission_id = _simple_submission(admin_client, user_client)

    resp = admin_client.post(f"/api/submissions/{submission_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived_by_me"] is True

    # The sender's list carries the flag; the signer's does not.
    sent = admin_client.get("/api/submissions", params={"mine": "sent"}).json()
    assert next(s for s in sent if s["id"] == submission_id)["archived_by_me"] is True
    sign = user_client.get("/api/submissions", params={"mine": "sign"}).json()
    assert next(s for s in sign if s["id"] == submission_id)["archived_by_me"] is False


def test_archive_is_idempotent_and_unarchive_restores(admin_client: TestClient, user_client: TestClient) -> None:
    submission_id = _simple_submission(admin_client, user_client)

    assert admin_client.post(f"/api/submissions/{submission_id}/archive").status_code == 200
    assert admin_client.post(f"/api/submissions/{submission_id}/archive").status_code == 200

    resp = admin_client.post(f"/api/submissions/{submission_id}/unarchive")
    assert resp.status_code == 200
    assert resp.json()["archived_by_me"] is False
    assert admin_client.post(f"/api/submissions/{submission_id}/unarchive").status_code == 200

    single = admin_client.get(f"/api/submissions/{submission_id}").json()
    assert single["archived_by_me"] is False


def test_archive_forbidden_for_bystander(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    submission_id = _simple_submission(admin_client, user_client)
    bystander = _login(make_client, app_settings, "bystander-archive@pumasi.ai", "Bystander")

    assert bystander.post(f"/api/submissions/{submission_id}/archive").status_code == 403
    assert bystander.post(f"/api/submissions/{submission_id}/unarchive").status_code == 403


# --- document preview ----------------------------------------------------


def test_document_preview_shows_partial_signatures(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """A pending envelope's preview stamps already-signed values with an
    In-progress watermark — later parties see earlier signers' work."""
    import io

    from pypdf import PdfReader

    template_id = _upload_template(admin_client, ["Signer 1", "Signer 2"])
    text_field = {
        "id": "t1",
        "type": "text",
        "role": "Signer 1",
        "page": 0,
        "x": 0.1,
        "y": 0.5,
        "w": 0.4,
        "h": 0.05,
        "required": True,
    }
    fields = admin_client.get(f"/api/templates/{template_id}").json()["fields"] + [text_field]
    assert admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields}).status_code == 200

    signer2 = _me_id(admin_client)
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Preview test",
            "signers": [
                {"role": "Signer 1", "user_id": _me_id(user_client)},
                {"role": "Signer 2", "user_id": signer2},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    submission_id = resp.json()["id"]

    # Signer 1 "signs" their text field directly in the DB (signature-image
    # fields would need a stored PNG; the text field proves the stamping).
    submitter = db.scalar(
        select(Submitter).where(Submitter.submission_id == submission_id, Submitter.role == "Signer 1"),
    )
    submitter.status = "completed"
    submitter.values = {"t1": "Signed by Jane Example"}
    db.commit()

    preview = admin_client.get(f"/api/files/document-preview/{submission_id}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "application/pdf"
    text = PdfReader(io.BytesIO(preview.content)).pages[0].extract_text()
    assert "Signed by Jane Example" in text
    assert "In progress" in text
    assert "Completed" not in text


def test_document_preview_access_rules(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Preview access")

    assert user_client.get(f"/api/files/document-preview/{submission_id}").status_code == 200

    bystander = _login(make_client, app_settings, "bystander-preview@pumasi.ai", "Bystander")
    assert bystander.get(f"/api/files/document-preview/{submission_id}").status_code == 403

    anonymous = make_client(app_settings)
    assert anonymous.get(f"/api/files/document-preview/{submission_id}").status_code == 401


def test_document_preview_serves_signed_pdf_when_completed(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    from app.storage import get_storage

    submission_id = _simple_submission(admin_client, user_client, title="Completed preview")
    signed_bytes = (FIXTURES / "sample.pdf").read_bytes()
    storage = get_storage(app_settings)
    storage.save(f"submissions/{submission_id}/signed.pdf", signed_bytes)
    submission = db.get(Submission, submission_id)
    submission.status = "completed"
    submission.signed_pdf_key = f"submissions/{submission_id}/signed.pdf"
    db.commit()

    preview = admin_client.get(f"/api/files/document-preview/{submission_id}")
    assert preview.status_code == 200
    assert preview.content == signed_bytes


# --- replace document (DocuSign-style Correct) ----------------------------


def _distinct_pdf(text: str, pages: int = 1) -> bytes:
    import io as _io

    from reportlab.pdfgen import canvas as _canvas

    buf = _io.BytesIO()
    c = _canvas.Canvas(buf)
    for i in range(pages):
        c.drawString(100, 700, f"{text} page {i + 1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _replace(client: TestClient, submission_id: int, pdf: bytes):
    return client.post(
        f"/api/submissions/{submission_id}/replace-document",
        files={"file": ("replacement.pdf", pdf, "application/pdf")},
    )


def test_replace_document_clones_shared_template_and_keeps_fields(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    import io as _io

    from pypdf import PdfReader

    template_id = _upload_template(admin_client, ["Signer 1"])
    original_fields = admin_client.get(f"/api/templates/{template_id}").json()["fields"]
    submission_id = _simple_submission(admin_client, user_client, title="Replace test")

    resp = _replace(admin_client, submission_id, _distinct_pdf("REPLACED DOC"))
    assert resp.status_code == 200, resp.text
    new_template_id = resp.json()["template"]["id"]

    # The shared template is untouched; the envelope points at a private clone.
    assert new_template_id != template_id
    original = admin_client.get(f"/api/templates/{template_id}").json()
    assert original["page_count"] == 2
    clone = admin_client.get(f"/api/templates/{new_template_id}").json()
    assert clone["fields"] == original_fields
    assert clone["page_count"] == 1
    # The clone never shows up as a reusable template.
    listed_ids = [t["id"] for t in admin_client.get("/api/templates").json()]
    assert new_template_id not in listed_ids
    assert template_id in listed_ids

    # The signer now sees the replaced document.
    preview = user_client.get(f"/api/files/document-preview/{submission_id}")
    assert preview.status_code == 200
    assert "REPLACED DOC" in PdfReader(_io.BytesIO(preview.content)).pages[0].extract_text()

    # Audit trail records the correction.
    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    corrected = [e for e in events if e["event"] == "corrected"]
    assert corrected and corrected[-1]["detail"]["changed"] == ["document"]


def test_replace_document_blocked_after_any_signature(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Signed already")
    submitter = db.scalar(select(Submitter).where(Submitter.submission_id == submission_id))
    submitter.status = "completed"
    db.commit()

    resp = _replace(admin_client, submission_id, _distinct_pdf("TOO LATE"))
    assert resp.status_code == 409
    assert "void" in resp.json()["detail"].lower()


def test_replace_document_rejects_document_with_too_few_pages(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    # Move the signature field to page 2 (sample.pdf has 2 pages).
    fields = admin_client.get(f"/api/templates/{template_id}").json()["fields"]
    fields[0]["page"] = 1
    assert admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields}).status_code == 200
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Page range",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    )
    submission_id = resp.json()["id"]

    replace_resp = _replace(admin_client, submission_id, _distinct_pdf("ONE PAGER", pages=1))
    assert replace_resp.status_code == 422
    assert "page 2" in replace_resp.json()["detail"]


def test_replace_document_sender_or_admin_only(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Perms")
    # The signer is a party but not the sender — still forbidden.
    assert _replace(user_client, submission_id, _distinct_pdf("NOPE")).status_code == 403


# --- download filenames ---------------------------------------------------


def test_document_preview_filename_matches_sharepoint_convention(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Vendor Agreement")

    resp = admin_client.get(f"/api/files/document-preview/{submission_id}")
    disposition = resp.headers["content-disposition"]
    assert "inline" in disposition
    assert "- in progress.pdf" in disposition
    assert "Vendor Agreement" in disposition
    # The internal id means nothing to users — it stays out of download names.
    assert f"({submission_id})" not in disposition


def test_filename_survives_korean_title(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    from urllib.parse import quote

    submission_id = _simple_submission(admin_client, user_client, title="한국 계약서")

    resp = admin_client.get(f"/api/files/document-preview/{submission_id}")
    disposition = resp.headers["content-disposition"]
    # RFC 5987 UTF-8 name carries the Korean; the plain filename= stays ASCII.
    assert quote("한국 계약서") in disposition
    assert "filename*=UTF-8''" in disposition


# --- void reason + recipient visibility -------------------------------------


def test_cancel_with_reason_records_audit_detail(admin_client: TestClient, user_client: TestClient) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Void reason test")

    resp = admin_client.post(f"/api/submissions/{submission_id}/cancel", json={"reason": "wrong counterparty"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    cancelled = [e for e in events if e["event"] == "cancelled"]
    assert cancelled and cancelled[-1]["detail"]["reason"] == "wrong counterparty"


def test_cancel_without_body_still_works(admin_client: TestClient, user_client: TestClient) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Bare void")

    resp = admin_client.post(f"/api/submissions/{submission_id}/cancel")
    assert resp.status_code == 200, resp.text

    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    cancelled = [e for e in events if e["event"] == "cancelled"]
    assert cancelled and "reason" not in (cancelled[-1]["detail"] or {})


def test_voided_envelope_still_listed_for_recipient(admin_client: TestClient, user_client: TestClient) -> None:
    """A voided envelope must not silently vanish from a recipient's list —
    they see it with its Voided status instead."""
    submission_id = _simple_submission(admin_client, user_client, title="Visible void")
    admin_client.post(f"/api/submissions/{submission_id}/cancel", json={"reason": "obsolete"})

    mine = user_client.get("/api/submissions", params={"mine": "sign"}).json()
    row = next((s for s in mine if s["id"] == submission_id), None)
    assert row is not None
    assert row["status"] == "cancelled"


def test_cc_recipient_sees_envelope_in_sign_list(
    admin_client: TestClient,
    user_client: TestClient,
    make_client,
    app_settings,
) -> None:
    """Inbox is "I'm a signer or CC" (envelope-browser spec) — CC-only
    recipients get in-app visibility, not just an email."""
    cc_client = make_client(app_settings)
    cc_client.post("/api/auth/dev-login", json={"email": "cc-inbox@pumasi.ai", "name": "CC Inbox"})
    cc_id = cc_client.get("/api/auth/me").json()["id"]

    template_id = _upload_template(admin_client, ["Signer 1"])
    submission_id = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "CC visibility",
            "signers": [
                {"role": "Signer 1", "user_id": _me_id(user_client)},
                {"user_id": cc_id, "is_cc": True},
            ],
        },
    ).json()["id"]

    mine = cc_client.get("/api/submissions", params={"mine": "sign"}).json()
    row = next((s for s in mine if s["id"] == submission_id), None)
    assert row is not None
    me_row = next(s for s in row["submitters"] if s["user"]["id"] == cc_id)
    assert me_row["is_cc"] is True


# --- recipient validation: dedupe + CC cap ----------------------------------


def test_duplicate_recipient_rejected(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    user_id = _me_id(user_client)

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Dup recipient",
            "signers": [
                {"role": "Signer 1", "user_id": user_id},
                {"user_id": user_id, "is_cc": True},
            ],
        },
    )
    assert resp.status_code == 422
    assert "more than once" in resp.json()["detail"]


def test_cc_cap_rejected(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    cc_ids = []
    for i in range(11):
        created = admin_client.post(
            "/api/users",
            json={"email": f"cc-cap-{i}@pumasi.ai", "name": f"CC {i}"},
        )
        assert created.status_code in (200, 201), created.text
        cc_ids.append(created.json()["id"])

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "CC cap",
            "signers": [
                {"role": "Signer 1", "user_id": _me_id(user_client)},
                *[{"user_id": cc_id, "is_cc": True} for cc_id in cc_ids],
            ],
        },
    )
    assert resp.status_code == 422
    assert "at most 10 CC" in resp.json()["detail"]


def test_replace_document_twice_reuses_the_clone(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """The private clone created by the first replace is is_adhoc, so a second
    replace overwrites it in place instead of orphaning template rows/files."""
    submission_id = _simple_submission(admin_client, user_client, title="Replace twice")
    original_template_id = admin_client.get(f"/api/submissions/{submission_id}").json()["template"]["id"]

    first = _replace(admin_client, submission_id, _distinct_pdf("VERSION TWO"))
    assert first.status_code == 200, first.text
    clone_id = first.json()["template"]["id"]
    assert clone_id != original_template_id

    second = _replace(admin_client, submission_id, _distinct_pdf("VERSION THREE"))
    assert second.status_code == 200, second.text
    assert second.json()["template"]["id"] == clone_id


# --- correction notifications ------------------------------------------------


def _capture_mailer(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        calls.append({"to": to, "subject": subject, "html": html_body})
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)
    return calls


def test_replace_document_notifies_contacted_signers(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Doc swap notice")

    sent = _capture_mailer(monkeypatch)
    resp = _replace(admin_client, submission_id, _distinct_pdf("NEW VERSION"))
    assert resp.status_code == 200, resp.text

    updates = [m for m in sent if m["subject"].startswith("Document updated:")]
    assert len(updates) == 1
    assert "replaced the document" in updates[0]["html"]


def test_replace_submitter_notifies_removed_signer(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Swap notice")
    old_email = user_client.get("/api/auth/me").json()["email"]

    replacement = admin_client.post(
        "/api/users",
        json={"email": "replacement-signer@pumasi.ai", "name": "Replacement"},
    ).json()

    submitters = admin_client.get(f"/api/submissions/{submission_id}").json()["submitters"]
    submitter_id = submitters[0]["id"]

    sent = _capture_mailer(monkeypatch)
    resp = admin_client.put(
        f"/api/submissions/{submission_id}/submitters/{submitter_id}",
        json={"user_id": replacement["id"]},
    )
    assert resp.status_code == 200, resp.text

    removed = [m for m in sent if m["subject"].startswith("Removed from:")]
    assert len(removed) == 1
    assert removed[0]["to"] == [old_email]
    invites = [m for m in sent if "requests your signature" in m["subject"]]
    assert any("replacement-signer@pumasi.ai" in m["to"] for m in invites)


# --- resend (bounce recovery) ------------------------------------------------


def test_resend_resets_reminder_budget_and_emails(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    """A bounced signer at the reminder cap can be re-invited: resend zeroes
    reminder_count and sends a fresh sign request."""
    submission_id = _simple_submission(admin_client, user_client, title="Bounce recovery")
    submitter = db.scalar(select(Submitter).where(Submitter.submission_id == submission_id))
    submitter.email_status = "failed"
    submitter.reminder_count = 3
    db.commit()
    submitter_id = submitter.id

    sent = _capture_mailer(monkeypatch)
    resp = admin_client.post(f"/api/submissions/{submission_id}/submitters/{submitter_id}/resend")
    assert resp.status_code == 200, resp.text

    assert any("requests your signature" in m["subject"] for m in sent)
    db.refresh(submitter)
    assert submitter.reminder_count == 0
    assert submitter.email_status == "sent"

    events = admin_client.get(f"/api/submissions/{submission_id}/events").json()
    resends = [e for e in events if e["event"] == "reminded" and (e["detail"] or {}).get("resend")]
    assert len(resends) == 1


def test_resend_out_of_turn_is_409(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    second_client = _login(make_client, app_settings, "resend-order@pumasi.ai", "Second")
    template_id = _upload_template(admin_client, ["Signer 1", "Signer 2"])
    submission = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Ordered resend",
            "signers": [
                {"role": "Signer 1", "user_id": _me_id(user_client), "order": 0},
                {"role": "Signer 2", "user_id": _me_id(second_client), "order": 1},
            ],
        },
    ).json()
    second_submitter = next(s for s in submission["submitters"] if s["user"]["id"] == _me_id(second_client))

    resp = admin_client.post(f"/api/submissions/{submission['id']}/submitters/{second_submitter['id']}/resend")
    assert resp.status_code == 409
    assert "turn" in resp.json()["detail"]


def test_resend_completed_submitter_is_409(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Resend done")
    submitter = db.scalar(select(Submitter).where(Submitter.submission_id == submission_id))
    submitter.status = "completed"
    db.commit()

    resp = admin_client.post(f"/api/submissions/{submission_id}/submitters/{submitter.id}/resend")
    assert resp.status_code == 409


def test_revoked_sender_loses_correction_rights_but_keeps_void(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Revoking can_send strips a sender's correction-type powers (remind,
    replace, edit) but never void — harm-reduction stays available."""
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(user_client, ["Signer 1"])
    submission_id = user_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": "Revoked", "signers": [{"role": "Signer 1", "user_id": admin_id}]},
    ).json()["id"]

    revoke = admin_client.put(f"/api/users/{user_id}", json={"can_send": False})
    assert revoke.status_code == 200, revoke.text

    assert user_client.post(f"/api/submissions/{submission_id}/remind").status_code == 403
    assert user_client.patch(f"/api/submissions/{submission_id}", json={"title": "New title"}).status_code == 403
    # Void still works: the envelope must not be stuck live in the wild.
    assert user_client.post(f"/api/submissions/{submission_id}/cancel").status_code == 200


def test_resend_forbidden_for_non_sender(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Resend perms")
    submitter = db.scalar(select(Submitter).where(Submitter.submission_id == submission_id))

    resp = user_client.post(f"/api/submissions/{submission_id}/submitters/{submitter.id}/resend")
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("status", "expected_note"),
    [("cancelled", "Voided"), ("declined", "Declined"), ("expired", "Expired")],
)
def test_document_preview_watermark_matches_terminal_status(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    status: str,
    expected_note: str,
) -> None:
    """A terminal envelope's preview must not masquerade as live: the
    per-page watermark says Voided/Declined/Expired instead of "In progress"
    (DocuSign stamps VOID for exactly this reason)."""
    import io

    from pypdf import PdfReader

    submission_id = _simple_submission(admin_client, user_client, title=f"Terminal {status}")
    submission = db.get(Submission, submission_id)
    submission.status = status
    db.commit()

    preview = admin_client.get(f"/api/files/document-preview/{submission_id}")
    assert preview.status_code == 200
    text = PdfReader(io.BytesIO(preview.content)).pages[0].extract_text()
    assert expected_note in text
    assert "In progress" not in text


# --- correct expiration & reminder settings (DocuSign "advanced options") --


def _last_corrected_detail(db: Session, submission_id: int) -> dict:
    event = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.submission_id == submission_id, AuditEvent.event == "corrected")
        .order_by(AuditEvent.id.desc()),
    ).first()
    assert event is not None, "expected a corrected audit event"
    return event.detail or {}


def test_correct_expiration_updates_deadline_and_resets_warning(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    from datetime import UTC, datetime, timedelta

    submission_id = _simple_submission(admin_client, user_client, title="Expiry edit")
    submission = db.get(Submission, submission_id)
    submission.expiry_warned_at = datetime.now(UTC)  # a warning already went out
    db.commit()

    new_deadline = datetime.now(UTC) + timedelta(days=14)
    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"expires_at": new_deadline.isoformat()},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["expires_at"] is not None

    db.expire_all()
    submission = db.get(Submission, submission_id)
    assert submission.expires_at == new_deadline
    # The old "expiring soon" send-once marker must not suppress a warning
    # for the *new* deadline.
    assert submission.expiry_warned_at is None
    assert _last_corrected_detail(db, submission_id)["changed"] == ["expires_at"]


def test_correct_expiration_explicit_null_clears_deadline(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    from datetime import UTC, datetime, timedelta

    submission_id = _simple_submission(admin_client, user_client, title="Expiry clear")
    submission = db.get(Submission, submission_id)
    submission.expires_at = datetime.now(UTC) + timedelta(days=3)
    db.commit()

    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"expires_at": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["expires_at"] is None

    db.expire_all()
    assert db.get(Submission, submission_id).expires_at is None


def test_correct_expiration_rejects_past_deadline(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    from datetime import UTC, datetime, timedelta

    submission_id = _simple_submission(admin_client, user_client, title="Expiry past")
    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat()},
    )
    assert resp.status_code == 422


def test_correct_reminder_settings(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Reminder edit")

    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"reminders_enabled": False, "reminder_interval_days": 7},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reminders_enabled"] is False
    assert body["reminder_interval_days"] == 7
    assert _last_corrected_detail(db, submission_id)["changed"] == [
        "reminders_enabled",
        "reminder_interval_days",
    ]


def test_correct_reminder_interval_out_of_range_rejected(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Reminder range")
    resp = admin_client.patch(f"/api/submissions/{submission_id}", json={"reminder_interval_days": 45})
    assert resp.status_code == 422


def test_correct_settings_noop_writes_no_audit_event(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """Sending the stored values back unchanged must not fabricate a
    correction in the audit trail (same rule as title/message)."""
    submission_id = _simple_submission(admin_client, user_client, title="Settings noop")

    resp = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"reminders_enabled": True, "reminder_interval_days": 3, "expires_at": None},
    )
    assert resp.status_code == 200, resp.text

    corrected = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission_id, AuditEvent.event == "corrected"),
    ).all()
    assert corrected == []


def test_stale_expiry_draft_is_rescued_by_correcting_the_deadline(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """The stale-expiry trap: a draft whose deadline passed can't be sent —
    correcting the deadline (now possible) must unblock it."""
    from datetime import UTC, datetime, timedelta

    template_id = _upload_template(admin_client, ["Signer 1"])
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Stale draft",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
            "draft": True,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    submission_id = resp.json()["id"]

    submission = db.get(Submission, submission_id)
    submission.expires_at = datetime.now(UTC) - timedelta(hours=1)  # deadline quietly passed
    db.commit()

    assert admin_client.post(f"/api/submissions/{submission_id}/send").status_code == 409

    fixed = admin_client.patch(
        f"/api/submissions/{submission_id}",
        json={"expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat()},
    )
    assert fixed.status_code == 200, fixed.text

    assert admin_client.post(f"/api/submissions/{submission_id}/send").status_code == 200


# --- form data (view + CSV export) ----------------------------------------


def _form_data_submission(admin_client: TestClient, user_client: TestClient, db: Session) -> int:
    """An envelope with signature+text+checkbox fields whose signer completed."""
    from datetime import UTC, datetime

    template_id = _upload_template(admin_client, ["Signer 1"])
    extra_fields = [
        {
            "id": "t1",
            "type": "text",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.5,
            "w": 0.4,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "c1",
            "type": "checkbox",
            "role": "Signer 1",
            "page": 0,
            "x": 0.6,
            "y": 0.5,
            "w": 0.05,
            "h": 0.05,
            "required": False,
        },
    ]
    fields = admin_client.get(f"/api/templates/{template_id}").json()["fields"] + extra_fields
    assert admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields}).status_code == 200

    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Form data test",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
        },
    )
    assert resp.status_code == 201, resp.text
    submission_id = resp.json()["id"]

    submitter = db.scalar(select(Submitter).where(Submitter.submission_id == submission_id))
    submitter.status = "completed"
    submitter.signed_at = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)
    submitter.values = {"t1": "Blue ink", "c1": True}
    db.commit()
    return submission_id


def test_form_data_lists_field_values_for_sender(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _form_data_submission(admin_client, user_client, db)

    resp = admin_client.get(f"/api/submissions/{submission_id}/form-data")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Form data test"

    by_field = {entry["field_id"]: entry for entry in body["entries"]}
    assert by_field["t1"]["value"] == "Blue ink"
    assert by_field["t1"]["field_type"] == "text"
    assert by_field["t1"]["recipient"]["email"] == "user@pumasi.ai"
    assert by_field["t1"]["signed_at"] is not None
    assert by_field["c1"]["value"] is True
    # Signature/initials are not data fields (DocuSign's rule) — excluded.
    assert "f0" not in by_field


def test_form_data_is_sender_or_admin_only(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    """Form data can contain other signers' entries — recipients don't get it."""
    submission_id = _form_data_submission(admin_client, user_client, db)

    assert user_client.get(f"/api/submissions/{submission_id}/form-data").status_code == 403
    bystander = _login(make_client, app_settings, "bystander-formdata@pumasi.ai", "Bystander")
    assert bystander.get(f"/api/submissions/{submission_id}/form-data").status_code == 403


def test_form_data_rejects_drafts(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, ["Signer 1"])
    resp = admin_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Draft form data",
            "signers": [{"role": "Signer 1", "user_id": _me_id(user_client)}],
            "draft": True,
        },
    )
    assert resp.status_code == 201, resp.text

    assert admin_client.get(f"/api/submissions/{resp.json()['id']}/form-data").status_code == 409


def test_form_data_csv_export(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _form_data_submission(admin_client, user_client, db)

    resp = admin_client.get(f"/api/submissions/{submission_id}/form-data", params={"format": "csv"})
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]

    lines = resp.text.strip().splitlines()
    header = lines[0]
    for column in ("envelope_id", "recipient_name", "recipient_email", "field_id", "field_type", "value"):
        assert column in header
    assert any("Blue ink" in line for line in lines[1:])
    assert any(",true" in line.lower() for line in lines[1:])  # checkbox exports as true/false


# --- save as template (DocuSign "Save as Template") ------------------------


def test_save_as_template_from_template_envelope(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """A reusable-template envelope becomes a new private template named
    after the envelope, carrying the document, fields, and roles."""
    submission_id = _simple_submission(admin_client, user_client, title="Quarterly NDA")

    resp = admin_client.post(f"/api/submissions/{submission_id}/save-as-template")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Quarterly NDA"
    assert body["roles"] == ["Signer 1"]
    assert [f["role"] for f in body["fields"]] == ["Signer 1"]
    assert body["shared"] is False

    # It lands in the caller's Templates list, usable for future sends.
    listed = admin_client.get("/api/templates").json()
    assert any(t["id"] == body["id"] for t in listed)
    # And its document file was really copied.
    assert admin_client.get(f"/api/files/template-pdf/{body['id']}").status_code == 200


def test_save_as_template_generalizes_adhoc_roles(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """Ad-hoc envelopes carry internal signer-N role ids — the saved template
    renames them to presentable "Signer N" roles (DocuSign's transformation)."""
    import json

    data = (FIXTURES / "sample.pdf").read_bytes()
    fields = [
        {
            "id": "s1",
            "type": "signature",
            "role": "signer-1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        },
        {
            "id": "s2",
            "type": "signature",
            "role": "signer-2",
            "page": 0,
            "x": 0.1,
            "y": 0.3,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        },
    ]
    resp = admin_client.post(
        "/api/submissions/adhoc",
        data={
            "title": "One-off offer",
            "signers_json": json.dumps(
                [
                    {"role": "signer-1", "user_id": _me_id(user_client)},
                    {"role": "signer-2", "user_id": _me_id(admin_client)},
                ],
            ),
            "fields_json": json.dumps(fields),
        },
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    submission_id = resp.json()["id"]

    saved = admin_client.post(f"/api/submissions/{submission_id}/save-as-template")
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["roles"] == ["Signer 1", "Signer 2"]
    assert sorted(f["role"] for f in body["fields"]) == ["Signer 1", "Signer 2"]


def test_save_as_template_is_sender_or_admin_only(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission_id = _simple_submission(admin_client, user_client, title="Not yours")
    # The signer (a non-sender party) may not turn the sender's envelope into
    # their own template.
    assert user_client.post(f"/api/submissions/{submission_id}/save-as-template").status_code == 403
