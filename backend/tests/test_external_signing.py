"""Tests for external-signer support: model columns, provisioning, token flow, decline."""

import re
from collections.abc import Generator
from unittest.mock import Mock

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app.auth import SIGNER_COOKIE_NAME, set_signer_cookie, signer_identity, signer_serializer
from app.config import Settings
from app.models import AuditEvent, Submission, Submitter, Template, User
from app.routers import signing as signing_router


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Generator[None, None, None]:
    """Module-level rate-limit state survives across TestClients; clear it per test."""
    signing_router._code_sends_by_uid.clear()
    signing_router._code_sends_by_ip.clear()
    yield
    signing_router._code_sends_by_uid.clear()
    signing_router._code_sends_by_ip.clear()


def test_declined_statuses_pass_check_constraints(db) -> None:
    user = User(email="ext@vendor.com", name="Ext Vendor", is_external=True)
    db.add(user)
    db.flush()
    template = Template(name="T", created_by=user.id, original_file_key="k", pdf_key="k", page_count=1)
    db.add(template)
    db.flush()
    submission = Submission(template_id=template.id, title="Doc", status="declined", created_by=user.id)
    db.add(submission)
    db.flush()
    submitter = Submitter(
        submission_id=submission.id,
        user_id=user.id,
        role="signer-1",
        status="declined",
        access_uid="a" * 32,
        decline_reason="not my contract",
    )
    db.add(submitter)
    db.add(AuditEvent(submission_id=submission.id, actor_user_id=user.id, event="declined"))
    db.commit()

    db.refresh(submitter)
    assert submitter.verification_attempts == 0
    assert user.is_external is True


def test_signer_cookie_round_trip() -> None:
    settings = Settings(session_secret="test-secret", app_base_url="http://testserver")
    response = Response()
    set_signer_cookie(response, 42, 7, settings)
    cookie_header = response.headers["set-cookie"]
    assert SIGNER_COOKIE_NAME in cookie_header and "HttpOnly" in cookie_header

    token = signer_serializer(settings).dumps({"sid": 42, "uid": 7})
    request = Mock(cookies={SIGNER_COOKIE_NAME: token})
    assert signer_identity(request, settings) == (42, 7)

    # Session-salt tokens must not be accepted as signer cookies.
    from app.auth import session_serializer

    wrong = session_serializer(settings).dumps({"sid": 42, "uid": 7})
    request = Mock(cookies={SIGNER_COOKIE_NAME: wrong})
    assert signer_identity(request, settings) is None


def test_signer_cookie_without_uid_claim_is_rejected() -> None:
    """A cookie signed before the ``uid`` claim existed (or otherwise missing it) must be
    treated as absent, never as sid-only trust — see the app.auth module docstring."""
    settings = Settings(session_secret="test-secret", app_base_url="http://testserver")
    legacy_token = signer_serializer(settings).dumps({"sid": 42})
    request = Mock(cookies={SIGNER_COOKIE_NAME: legacy_token})
    assert signer_identity(request, settings) is None


# --- helpers reused by later tasks -------------------------------------------


def _capture_mail(monkeypatch) -> list[dict]:
    """Monkeypatch mailer.send, capturing every send as a dict."""
    from app import mailer

    sent: list[dict] = []

    def fake_send(settings, to, subject, body, attachments=None):
        sent.append({"to": list(to), "subject": subject, "body": body, "attachments": attachments or []})
        return True

    monkeypatch.setattr(mailer, "send", fake_send)
    return sent


def _last_code(sent: list[dict]) -> str:
    match = re.search(r"\b(\d{6})\b", sent[-1]["body"])
    assert match, f"no 6-digit code in: {sent[-1]['body']}"
    return match.group(1)


def _provision_external(admin_client: TestClient, email: str = "ext@vendor.com", name: str = "Ext Vendor") -> int:
    resp = admin_client.post("/api/users", json={"email": email, "name": name})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _external_submission(admin_client: TestClient, db) -> tuple[dict, str, int]:
    """One-external-signer submission; returns (submission_json, access_uid, submitter_id)."""
    from sqlalchemy import select

    from app.models import Submitter
    from tests.test_signing import _create_submission, _field, _upload_template

    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    ext_id = _provision_external(admin_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": ext_id}])
    submitter_id = submission["submitters"][0]["id"]
    access_uid = db.scalars(select(Submitter.access_uid).where(Submitter.id == submitter_id)).one()
    assert access_uid, "external submitter should have an access_uid"
    return submission, access_uid, submitter_id


# --- token endpoints ----------------------------------------------------------


def test_token_landing_masks_email(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    _capture_mail(monkeypatch)
    _submission, access_uid, _sid = _external_submission(admin_client, db)
    anon = make_client(app_settings)

    resp = anon.get(f"/api/sign/token/{access_uid}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "open"
    assert body["masked_email"] == "e***@vendor.com"
    assert body["title"] == "Doc"
    assert anon.get("/api/sign/token/" + "0" * 32).status_code == 404


def test_verify_flow_sets_cookie_and_scopes_it(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    sent = _capture_mail(monkeypatch)
    _submission, access_uid, submitter_id = _external_submission(admin_client, db)
    anon = make_client(app_settings)

    assert anon.post(f"/api/sign/token/{access_uid}/request-code").status_code == 200
    code = _last_code(sent)

    wrong = anon.post(f"/api/sign/token/{access_uid}/verify", json={"code": "000000" if code != "000000" else "111111"})
    assert wrong.status_code == 401

    ok = anon.post(f"/api/sign/token/{access_uid}/verify", json={"code": code})
    assert ok.status_code == 200
    assert ok.json() == {"submitter_id": submitter_id}
    assert "sign_signer" in anon.cookies


def test_verify_locks_out_after_five_wrong_attempts(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    sent = _capture_mail(monkeypatch)
    _submission, access_uid, _sid = _external_submission(admin_client, db)
    anon = make_client(app_settings)
    anon.post(f"/api/sign/token/{access_uid}/request-code")
    code = _last_code(sent)
    bad = "999999" if code != "999999" else "888888"

    for _ in range(5):
        assert anon.post(f"/api/sign/token/{access_uid}/verify", json={"code": bad}).status_code == 401
    # Code invalidated: even the right one is now rejected until re-requested.
    assert anon.post(f"/api/sign/token/{access_uid}/verify", json={"code": code}).status_code == 410


def test_request_code_rate_limited_per_submitter(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    _capture_mail(monkeypatch)
    _submission, access_uid, _sid = _external_submission(admin_client, db)
    anon = make_client(app_settings)

    for _ in range(3):
        assert anon.post(f"/api/sign/token/{access_uid}/request-code").status_code == 200
    assert anon.post(f"/api/sign/token/{access_uid}/request-code").status_code == 429


def test_request_code_survives_mail_failure_under_dev_bypass(
    admin_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
    tmp_path,
) -> None:
    """A dev/e2e box normally has no real Graph mail credentials configured,

    so ``mailer.send`` always returns ``False`` there — the ``dev_code``
    escape hatch has to survive that or it's useless for e2e tests, which
    can't read the signer's mailbox either way. In production
    (``dev_auth_bypass=False``) a real send failure must still 502.
    """
    from app import mailer

    monkeypatch.setattr(mailer, "send", lambda *a, **k: False)
    _submission, access_uid, _sid = _external_submission(admin_client, db)

    anon = make_client(app_settings)
    resp = anon.post(f"/api/sign/token/{access_uid}/request-code")
    assert resp.status_code == 200
    assert re.fullmatch(r"\d{6}", resp.json()["dev_code"])

    prod_settings = Settings(
        session_secret="test-session-secret",
        app_base_url="http://testserver",
        data_dir=str(tmp_path),
    )
    prod_anon = make_client(prod_settings)
    assert prod_anon.post(f"/api/sign/token/{access_uid}/request-code").status_code == 502


# --- signing routes via the signer cookie ------------------------------------


def _verified_anon(admin_client, make_client, app_settings, db, monkeypatch):
    """Anonymous client holding a valid signer cookie; returns (anon, submission, submitter_id, sent)."""
    sent = _capture_mail(monkeypatch)
    submission, access_uid, submitter_id = _external_submission(admin_client, db)
    anon = make_client(app_settings)
    anon.post(f"/api/sign/token/{access_uid}/request-code")
    resp = anon.post(f"/api/sign/token/{access_uid}/verify", json={"code": _last_code(sent)})
    assert resp.status_code == 200, resp.text
    return anon, submission, submitter_id, sent


def test_signer_cookie_grants_sign_view_with_my_name(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    anon, _submission, submitter_id, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)

    resp = anon.get(f"/api/sign/{submitter_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["my_name"] == "Ext Vendor"
    assert body["my_status"] == "opened"
    # No session -> the "use saved signature" shortcut is pointless (GET
    # /api/files/signature/{id} is session-only), so it's never offered.
    assert body["saved_signature_id"] is None


def test_signer_cookie_cannot_touch_other_submitters_or_app_apis(
    admin_client,
    user_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    from tests.test_signing import _create_submission, _field, _me_id, _submitter_id_for, _upload_template

    anon, _submission, _sid, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    template_id = _upload_template(admin_client, [_field("sig9", "signature", "Signer 1")], name="Other")
    internal_id = _me_id(user_client)
    other = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": internal_id}])
    other_submitter = _submitter_id_for(other, internal_id)

    assert anon.get(f"/api/sign/{other_submitter}").status_code == 403
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.get("/api/users").status_code == 401


def test_replaced_external_signers_old_cookie_is_rejected(
    admin_client,
    user_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    """After replace_submitter swaps the signer, the OLD signer's still-valid
    sign_signer cookie must not keep granting access to either sign route —
    regression test for the uid-bound cookie fix (app.auth.signer_identity).
    """
    from tests.test_signing import _me_id

    anon, submission, submitter_id, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    new_user_id = _me_id(user_client)

    replace_resp = admin_client.put(
        f"/api/submissions/{submission['id']}/submitters/{submitter_id}",
        json={"user_id": new_user_id},
    )
    assert replace_resp.status_code == 200, replace_resp.text

    assert anon.get(f"/api/sign/{submitter_id}").status_code == 403
    complete_resp = anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {}})
    assert complete_resp.status_code == 403


def test_external_signer_completes_via_cookie(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)

    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})
    assert sig.status_code == 200, sig.text
    done = anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig.json()["signature_id"]}})
    assert done.status_code == 200, done.text

    detail = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert detail["status"] == "completed"


# --- file routes via the signer cookie -------------------------------------------


def test_signer_cookie_grants_template_pdf_for_own_envelope_only(
    admin_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    from tests.test_signing import _field, _upload_template

    anon, submission, _sid, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    own_template = submission["template"]["id"]
    other_template = _upload_template(admin_client, [_field("x", "signature", "Signer 1")], name="Unrelated")

    assert anon.get(f"/api/files/template-pdf/{own_template}").status_code == 200
    assert anon.get(f"/api/files/template-pdf/{other_template}").status_code == 403


def test_signer_cookie_grants_signed_pdf_after_completion(
    admin_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL}).json()["signature_id"]
    anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig}})

    assert anon.get(f"/api/files/signed-pdf/{submission['id']}").status_code == 200
    assert anon.get(f"/api/files/certificate/{submission['id']}").status_code == 401


def test_completed_envelope_code_flow_still_works_for_retrieval(
    admin_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    """A signer re-opening their emailed link after completion can verify
    again (fresh browser, expired cookie) and download the executed PDF —
    previously the code endpoints 409'd on anything not "open"."""
    from app.models import Submitter
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL}).json()["signature_id"]
    assert anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig}}).status_code == 200

    access_uid = db.get(Submitter, submitter_id).access_uid
    fresh = make_client(app_settings)

    landing = fresh.get(f"/api/sign/token/{access_uid}")
    assert landing.status_code == 200
    assert landing.json()["status"] == "completed"

    assert fresh.post(f"/api/sign/token/{access_uid}/request-code").status_code == 200
    verify = fresh.post(f"/api/sign/token/{access_uid}/verify", json={"code": _last_code(sent)})
    assert verify.status_code == 200, verify.text

    assert fresh.get(f"/api/files/signed-pdf/{submission['id']}").status_code == 200


def test_voided_envelope_code_flow_still_blocked(
    admin_client,
    make_client,
    app_settings,
    db,
    monkeypatch,
) -> None:
    anon, submission, _submitter_id, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    from app.models import Submitter

    assert admin_client.post(f"/api/submissions/{submission['id']}/cancel").status_code == 200

    access_uid = db.get(Submitter, _submitter_id).access_uid
    fresh = make_client(app_settings)
    assert fresh.post(f"/api/sign/token/{access_uid}/request-code").status_code == 409


def test_decline_voids_envelope_and_notifies_sender(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    anon, submission, submitter_id, sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)

    resp = anon.post(f"/api/sign/{submitter_id}/decline", json={"reason": "Wrong entity name"})

    assert resp.status_code == 200
    detail = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert detail["status"] == "declined"
    assert detail["submitters"][0]["status"] == "declined"

    events = admin_client.get(f"/api/submissions/{submission['id']}/events").json()
    declined = next(e for e in events if e["event"] == "declined")
    assert declined["detail"]["reason"] == "Wrong entity name"
    assert declined["actor"]["name"] == "Ext Vendor"

    decline_mail = next(m for m in sent if m["subject"].startswith("Declined:"))
    assert "admin@pumasi.ai" in decline_mail["to"]
    assert "Wrong entity name" in decline_mail["body"]

    # Envelope is void: further signing/declining 409s, as does cancel.
    assert anon.post(f"/api/sign/{submitter_id}/decline", json={"reason": None}).status_code == 409
    assert anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {}}).status_code == 409
    assert admin_client.post(f"/api/submissions/{submission['id']}/cancel").status_code == 409


def test_dev_signing_links_gated_by_bypass(admin_client, make_client, db, monkeypatch, tmp_path) -> None:
    _capture_mail(monkeypatch)
    submission, access_uid, submitter_id = _external_submission(admin_client, db)

    resp = admin_client.get(f"/api/submissions/{submission['id']}/dev-signing-links")
    assert resp.status_code == 200
    assert resp.json() == [{"submitter_id": submitter_id, "access_uid": access_uid}]

    prod_settings = Settings(
        session_secret="test-session-secret",
        app_base_url="http://testserver",
        data_dir=str(tmp_path),
    )
    prod_client = make_client(prod_settings)
    assert prod_client.get(f"/api/submissions/{submission['id']}/dev-signing-links").status_code in (401, 404)


def test_internal_signer_can_decline_too(admin_client, user_client) -> None:
    from tests.test_signing import _create_submission, _field, _me_id, _submitter_id_for, _upload_template

    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": _me_id(user_client)}])
    submitter_id = _submitter_id_for(submission, _me_id(user_client))

    assert user_client.post(f"/api/sign/{submitter_id}/decline", json={"reason": None}).status_code == 200
    assert admin_client.get(f"/api/submissions/{submission['id']}").json()["status"] == "declined"
