"""Tests for the submitter-facing signing API (GET/POST /api/sign/{submitter_id}...)."""

import base64
import io
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app import completion, notifications
from app.config import Settings
from app.models import AuditEvent, Signature, Submission, Submitter, User
from app.storage import get_storage
from tests.conftest import TEST_DATABASE_URL

FIXTURES = Path(__file__).parent / "fixtures"

# A real (tiny, 1x1) PNG, base64-encoded.
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
PNG_DATA_URL = f"data:image/png;base64,{PNG_B64}"
PNG_MAGIC_BYTES = b"\x89PNG\r\n\x1a\n"


def _upload_template(admin_client: TestClient, fields: list[dict], *, name: str = "Doc") -> int:
    """Upload sample.pdf as admin and set ``fields`` (full FieldDef dicts) on it."""
    data = (FIXTURES / "sample.pdf").read_bytes()
    resp = admin_client.post(
        "/api/templates",
        data={"name": name},
        files={"file": ("sample.pdf", data, "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    template_id = resp.json()["id"]

    fields_resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields})
    assert fields_resp.status_code == 200, fields_resp.text
    return template_id


def _field(field_id: str, field_type: str, role: str, *, x: float = 0.1, required: bool = True) -> dict:
    return {
        "id": field_id,
        "type": field_type,
        "role": role,
        "page": 0,
        "x": x,
        "y": 0.1,
        "w": 0.2,
        "h": 0.05,
        "required": required,
    }


def _create_submission(admin_client: TestClient, template_id: int, signers: list[dict], *, title: str = "Doc") -> dict:
    resp = admin_client.post(
        "/api/submissions",
        json={"template_id": template_id, "title": title, "signers": signers},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _submitter_id_for(submission: dict, user_id: int) -> int:
    for submitter in submission["submitters"]:
        if submitter["user"]["id"] == user_id:
            return submitter["id"]
    raise AssertionError(f"no submitter for user {user_id} in {submission}")


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


def _single_signer_submission(admin_client: TestClient, signer_client: TestClient) -> tuple[dict, int]:
    """Create a one-signer, one-signature-field submission; return (submission, submitter_id)."""
    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    signer_id = _me_id(signer_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": signer_id}])
    submitter_id = _submitter_id_for(submission, signer_id)
    return submission, submitter_id


# --- GET /api/sign/{submitter_id} -------------------------------------------


def test_get_sign_view_unknown_submitter_is_404(user_client: TestClient) -> None:
    response = user_client.get("/api/sign/999999")

    assert response.status_code == 404


def test_get_sign_view_other_user_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    bystander = _login(make_client, app_settings, "bystander@pumasi.ai", "Bystander")
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = bystander.get(f"/api/sign/{submitter_id}")

    assert response.status_code == 403


def test_get_sign_view_flips_pending_to_opened_once(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = user_client.get(f"/api/sign/{submitter_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["my_status"] == "opened"
    assert body["submission"]["id"] == submission["id"]
    assert body["submission"]["status"] == "pending"
    assert body["template"]["id"] == submission["template"]["id"]
    assert body["my_fields"] == ["sig1"]
    assert body["saved_signature_id"] is None

    submitter = db.get(Submitter, submitter_id)
    assert submitter.status == "opened"

    opened_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "opened"),
    ).all()
    assert len(opened_events) == 1
    assert opened_events[0].actor_user_id == _me_id(user_client)
    assert opened_events[0].ip_address is not None

    # Second GET must not flip again or write a second "opened" event.
    response2 = user_client.get(f"/api/sign/{submitter_id}")
    assert response2.status_code == 200
    assert response2.json()["my_status"] == "opened"

    opened_events_again = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "opened"),
    ).all()
    assert len(opened_events_again) == 1


def test_get_sign_view_includes_role_names_for_every_submitter(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    """``role_names`` maps every submitter's role to their real display
    name, not the raw role string — the frontend uses this to label
    co-signers' (read-only) fields by name. This matters most for ad-hoc
    envelopes, where the role is an internal ``signer-N`` string never meant
    to be user-facing, but is returned for template envelopes too."""
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)
    template_id = _upload_template(
        admin_client,
        [_field("sig1", "signature", "Signer 1"), _field("sig2", "signature", "Signer 2", x=0.4)],
    )
    submission = _create_submission(
        admin_client,
        template_id,
        [{"role": "Signer 1", "user_id": user_id}, {"role": "Signer 2", "user_id": admin_id}],
    )
    submitter_id = _submitter_id_for(submission, user_id)

    response = user_client.get(f"/api/sign/{submitter_id}")

    assert response.status_code == 200
    assert response.json()["role_names"] == {"Signer 1": "User", "Signer 2": "Admin"}


def test_get_sign_view_does_not_flip_when_submission_cancelled(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission, submitter_id = _single_signer_submission(admin_client, user_client)

    cancel_resp = admin_client.post(f"/api/submissions/{submission['id']}/cancel")
    assert cancel_resp.status_code == 200

    response = user_client.get(f"/api/sign/{submitter_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["my_status"] == "pending"
    assert body["submission"]["status"] == "cancelled"

    submitter = db.get(Submitter, submitter_id)
    assert submitter.status == "pending"

    opened_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "opened"),
    ).all()
    assert opened_events == []


def test_get_sign_view_reports_latest_saved_signature(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    upload_resp = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})
    assert upload_resp.status_code == 200
    signature_id = upload_resp.json()["signature_id"]

    view_resp = user_client.get(f"/api/sign/{submitter_id}")
    assert view_resp.json()["saved_signature_id"] == signature_id


# --- POST /api/sign/{submitter_id}/signature --------------------------------


def test_upload_signature_unknown_submitter_is_404(user_client: TestClient) -> None:
    response = user_client.post("/api/sign/999999/signature", json={"image": PNG_DATA_URL})

    assert response.status_code == 404


def test_upload_signature_other_user_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    bystander = _login(make_client, app_settings, "bystander2@pumasi.ai", "Bystander")
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = bystander.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})

    assert response.status_code == 403


def test_upload_signature_stores_file_and_row(
    admin_client: TestClient,
    user_client: TestClient,
    app_settings: Settings,
    db: Session,
) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})

    assert response.status_code == 200
    signature_id = response.json()["signature_id"]
    signature = db.get(Signature, signature_id)
    assert signature is not None
    assert signature.user_id == _me_id(user_client)
    assert signature.image_key.startswith(f"signatures/{signature.user_id}/")
    assert (Path(app_settings.data_dir) / signature.image_key).is_file()


def test_upload_signature_bad_prefix_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    bad_image = f"data:image/jpeg;base64,{PNG_B64}"
    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": bad_image})

    assert response.status_code == 422


def test_upload_signature_invalid_base64_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": "data:image/png;base64,not-valid-base64!!!"},
    )

    assert response.status_code == 422


def test_upload_signature_oversized_is_413(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)
    # Real PNG magic bytes so this fails the *size* check specifically,
    # not the magic-byte check (that has its own dedicated test below).
    huge = base64.b64encode(PNG_MAGIC_BYTES + b"0" * (1024 * 1024 + 1)).decode()

    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": f"data:image/png;base64,{huge}"})

    assert response.status_code == 413


def test_upload_signature_non_png_bytes_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)
    # Valid base64, well under the size limit, real JPEG magic bytes — but not a PNG.
    jpeg_ish = base64.b64encode(b"\xff\xd8\xff\xe0this is not a png").decode()
    bad_image = f"data:image/png;base64,{jpeg_ish}"

    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": bad_image})

    assert response.status_code == 422


def test_upload_signature_empty_payload_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": "data:image/png;base64,"})

    assert response.status_code == 422


def test_upload_signature_after_completed_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)
    upload_resp = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})
    signature_id = upload_resp.json()["signature_id"]

    complete_resp = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id}},
    )
    assert complete_resp.status_code == 200

    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})

    assert response.status_code == 409


def test_upload_signature_on_cancelled_submission_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    admin_client.post(f"/api/submissions/{submission['id']}/cancel")

    response = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})

    assert response.status_code == 409


# --- POST /api/sign/{submitter_id}/complete ---------------------------------


def test_complete_unknown_submitter_is_404(user_client: TestClient) -> None:
    response = user_client.post("/api/sign/999999/complete", json={"values": {}})

    assert response.status_code == 404


def test_complete_other_user_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    bystander = _login(make_client, app_settings, "bystander3@pumasi.ai", "Bystander")
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = bystander.post(f"/api/sign/{submitter_id}/complete", json={"values": {}})

    assert response.status_code == 403


def test_complete_missing_required_field_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {}})

    assert response.status_code == 422


def test_complete_unknown_field_id_is_422(admin_client: TestClient, user_client: TestClient) -> None:
    _submission, submitter_id = _single_signer_submission(admin_client, user_client)
    upload_resp = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})
    signature_id = upload_resp.json()["signature_id"]

    response = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "not-a-real-field": "x"}},
    )

    assert response.status_code == 422


def test_complete_signature_field_requires_ownership(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    other = _login(make_client, app_settings, "other-owner@pumasi.ai", "Other")
    # `other` isn't a submitter anywhere yet — give them a signature id via a
    # submission of their own, then try to use it on `user_client`'s submission.
    template_id = _upload_template(admin_client, [_field("sigX", "signature", "Signer 1")], name="OtherDoc")
    other_submission = _create_submission(
        admin_client,
        template_id,
        [{"role": "Signer 1", "user_id": _me_id(other)}],
    )
    other_submitter_id = _submitter_id_for(other_submission, _me_id(other))
    other_signature_resp = other.post(f"/api/sign/{other_submitter_id}/signature", json={"image": PNG_DATA_URL})
    assert other_signature_resp.status_code == 200
    other_signature_id = other_signature_resp.json()["signature_id"]

    _submission, submitter_id = _single_signer_submission(admin_client, user_client)

    response = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": other_signature_id}},
    )

    assert response.status_code == 422


def test_complete_date_checkbox_text_validation(admin_client: TestClient, user_client: TestClient) -> None:
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("date1", "date", "Signer 1", x=0.4),
        _field("chk1", "checkbox", "Signer 1", x=0.6, required=False),
        _field("txt1", "text", "Signer 1", x=0.8, required=False),
    ]
    template_id = _upload_template(admin_client, fields)
    signer_id = _me_id(user_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": signer_id}])
    submitter_id = _submitter_id_for(submission, signer_id)

    signature_id = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]

    # bad date format
    bad_date = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "date1": "07/30/2026"}},
    )
    assert bad_date.status_code == 422

    # bad checkbox type
    bad_checkbox = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "date1": "2026-07-30", "chk1": "yes"}},
    )
    assert bad_checkbox.status_code == 422

    # text too long
    bad_text = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "date1": "2026-07-30", "txt1": "x" * 501}},
    )
    assert bad_text.status_code == 422

    # valid values succeed
    good = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "date1": "2026-07-30", "chk1": True, "txt1": "looks good"}},
    )
    assert good.status_code == 200, good.text
    assert good.json() == {"already": False}


def test_complete_required_name_field_never_blocks(admin_client: TestClient, user_client: TestClient) -> None:
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("name1", "name", "Signer 1", x=0.4, required=True),
    ]
    template_id = _upload_template(admin_client, fields)
    signer_id = _me_id(user_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": signer_id}])
    submitter_id = _submitter_id_for(submission, signer_id)
    signature_id = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]

    response = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id}},
    )

    assert response.status_code == 200
    assert response.json() == {"already": False}


def test_complete_validates_name_value_when_supplied(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """Name fields are editable: a supplied value is validated like text
    (string, <=500 chars) and stored; omitting it still works (server falls
    back to the account name at stamping time)."""
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("name1", "name", "Signer 1", x=0.4),
    ]
    template_id = _upload_template(admin_client, fields)
    signer_id = _me_id(user_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": signer_id}])
    submitter_id = _submitter_id_for(submission, signer_id)
    signature_id = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]

    not_a_string = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "name1": 123}},
    )
    assert not_a_string.status_code == 422

    too_long = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "name1": "x" * 501}},
    )
    assert too_long.status_code == 422

    good = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "name1": "Preferred Name"}},
    )
    assert good.status_code == 200, good.text

    submitter = db.get(Submitter, submitter_id)
    db.refresh(submitter)
    assert submitter.values["name1"] == "Preferred Name"


def test_ordered_signing_blocks_second_signer_until_first_completes(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    second_client = _login(make_client, app_settings, "second-signer@pumasi.ai", "Second Signer")
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("sig2", "signature", "Signer 2", x=0.5),
    ]
    template_id = _upload_template(admin_client, fields)
    first_id = _me_id(user_client)
    second_id = _me_id(second_client)
    submission = _create_submission(
        admin_client,
        template_id,
        [
            {"role": "Signer 1", "user_id": first_id, "order": 0},
            {"role": "Signer 2", "user_id": second_id, "order": 1},
        ],
    )
    first_submitter = _submitter_id_for(submission, first_id)
    second_submitter = _submitter_id_for(submission, second_id)

    # Second signer's view says it's not their turn yet.
    view = second_client.get(f"/api/sign/{second_submitter}")
    assert view.status_code == 200
    assert view.json()["my_turn"] is False

    # Completing out of turn is rejected.
    sig = second_client.post(f"/api/sign/{second_submitter}/signature", json={"image": PNG_DATA_URL})
    blocked = second_client.post(
        f"/api/sign/{second_submitter}/complete",
        json={"values": {"sig2": sig.json()["signature_id"]}},
    )
    assert blocked.status_code == 409

    # First signer completes; now it's the second signer's turn.
    first_sig = user_client.post(f"/api/sign/{first_submitter}/signature", json={"image": PNG_DATA_URL})
    done = user_client.post(
        f"/api/sign/{first_submitter}/complete",
        json={"values": {"sig1": first_sig.json()["signature_id"]}},
    )
    assert done.status_code == 200, done.text

    assert second_client.get(f"/api/sign/{second_submitter}").json()["my_turn"] is True
    unblocked = second_client.post(
        f"/api/sign/{second_submitter}/complete",
        json={"values": {"sig2": sig.json()["signature_id"]}},
    )
    assert unblocked.status_code == 200, unblocked.text


def test_cc_recipient_cannot_use_signing_routes_and_never_blocks_completion(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    cc_client = _login(make_client, app_settings, "cc-viewer@pumasi.ai", "CC Viewer")
    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    signer_id = _me_id(user_client)
    cc_id = _me_id(cc_client)
    submission = _create_submission(
        admin_client,
        template_id,
        [
            {"role": "Signer 1", "user_id": signer_id},
            {"user_id": cc_id, "is_cc": True, "order": 1},
        ],
    )
    signer_submitter = _submitter_id_for(submission, signer_id)
    cc_submitter = _submitter_id_for(submission, cc_id)

    # CC rows have nothing to sign — the signing view rejects them.
    assert cc_client.get(f"/api/sign/{cc_submitter}").status_code == 409

    # The only signer completing finishes the envelope; the pending CC row
    # doesn't hold it open.
    signature_id = user_client.post(
        f"/api/sign/{signer_submitter}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]
    done = user_client.post(
        f"/api/sign/{signer_submitter}/complete",
        json={"values": {"sig1": signature_id}},
    )
    assert done.status_code == 200, done.text

    detail = admin_client.get(f"/api/submissions/{submission['id']}")
    assert detail.json()["status"] == "completed"


def test_initials_field_signs_like_a_signature(admin_client: TestClient, user_client: TestClient) -> None:
    """Initials validate and store exactly like signatures: an owned
    signature id; a bogus value type is rejected."""
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("ini1", "initials", "Signer 1", x=0.5),
    ]
    template_id = _upload_template(admin_client, fields)
    signer_id = _me_id(user_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": signer_id}])
    submitter_id = _submitter_id_for(submission, signer_id)

    signature_id = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]
    initials_id = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]

    bad = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "ini1": "not-an-id"}},
    )
    assert bad.status_code == 422

    good = user_client.post(
        f"/api/sign/{submitter_id}/complete",
        json={"values": {"sig1": signature_id, "ini1": initials_id}},
    )
    assert good.status_code == 200, good.text


def test_complete_double_complete_is_idempotent(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    signature_id = user_client.post(
        f"/api/sign/{submitter_id}/signature",
        json={"image": PNG_DATA_URL},
    ).json()["signature_id"]

    first = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": signature_id}})
    assert first.status_code == 200
    assert first.json() == {"already": False}

    second = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": signature_id}})
    assert second.status_code == 200
    assert second.json() == {"already": True}

    signed_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "signed"),
    ).all()
    assert len(signed_events) == 1


def test_complete_on_cancelled_submission_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    admin_client.post(f"/api/submissions/{submission['id']}/cancel")

    response = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {}})

    assert response.status_code == 409


def test_complete_last_signer_flips_submission_to_completed(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    signer2 = _login(make_client, app_settings, "signer2@pumasi.ai", "Signer Two")

    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("sig2", "signature", "Signer 2", x=0.5),
    ]
    template_id = _upload_template(admin_client, fields)
    user_id = _me_id(user_client)
    signer2_id = _me_id(signer2)
    submission = _create_submission(
        admin_client,
        template_id,
        [{"role": "Signer 1", "user_id": user_id}, {"role": "Signer 2", "user_id": signer2_id}],
    )
    submitter1_id = _submitter_id_for(submission, user_id)
    submitter2_id = _submitter_id_for(submission, signer2_id)

    sig1_resp = user_client.post(f"/api/sign/{submitter1_id}/signature", json={"image": PNG_DATA_URL})
    sig1_id = sig1_resp.json()["signature_id"]
    sig2_resp = signer2.post(f"/api/sign/{submitter2_id}/signature", json={"image": PNG_DATA_URL})
    sig2_id = sig2_resp.json()["signature_id"]

    first = user_client.post(f"/api/sign/{submitter1_id}/complete", json={"values": {"sig1": sig1_id}})
    assert first.status_code == 200

    # Only one of two submitters done -> submission still pending, no "completed" audit event yet.
    sub_resp = admin_client.get(f"/api/submissions/{submission['id']}")
    assert sub_resp.json()["status"] == "pending"
    completed_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "completed"),
    ).all()
    assert completed_events == []

    second = signer2.post(f"/api/sign/{submitter2_id}/complete", json={"values": {"sig2": sig2_id}})
    assert second.status_code == 200

    sub_resp2 = admin_client.get(f"/api/submissions/{submission['id']}")
    body = sub_resp2.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None

    completed_events2 = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "completed"),
    ).all()
    assert len(completed_events2) == 1
    assert completed_events2[0].actor_user_id is None


def test_complete_self_heals_a_stranded_submission(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    """Regression test for the concurrent-last-signer race in ``_maybe_finalize``.

    What this test *can't* do: reliably force two ``/complete`` requests to
    interleave inside the same READ COMMITTED transaction window against a
    synchronous ``TestClient`` — that would need real thread-level control
    over statement timing, which this suite doesn't have. So this is not a
    true concurrency test and doesn't exercise the ``SELECT ... FOR
    UPDATE`` lock itself.

    What it *does* verify honestly: the specific failure mode the lock
    exists to prevent — a submission stuck at "pending" with every
    submitter already "completed" — self-heals. That stranded state is
    built directly here (bypassing the router for submitter2's completion,
    which is exactly what a lost race would produce: submitter2 marked
    completed with no finalize check ever having run for it), then the
    very next ``/complete`` call — even the idempotent
    already-completed branch for submitter1 — is asserted to notice and
    finalize rather than silently no-op.
    """
    signer2 = _login(make_client, app_settings, "signer2-heal@pumasi.ai", "Signer Two")

    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("sig2", "signature", "Signer 2", x=0.5),
    ]
    template_id = _upload_template(admin_client, fields)
    user_id = _me_id(user_client)
    signer2_id = _me_id(signer2)
    submission = _create_submission(
        admin_client,
        template_id,
        [{"role": "Signer 1", "user_id": user_id}, {"role": "Signer 2", "user_id": signer2_id}],
    )
    submitter1_id = _submitter_id_for(submission, user_id)
    submitter2_id = _submitter_id_for(submission, signer2_id)

    sig1_resp = user_client.post(f"/api/sign/{submitter1_id}/signature", json={"image": PNG_DATA_URL})
    sig1_id = sig1_resp.json()["signature_id"]

    first = user_client.post(f"/api/sign/{submitter1_id}/complete", json={"values": {"sig1": sig1_id}})
    assert first.status_code == 200

    # Simulate the stranded outcome of a lost finalize race: mark
    # submitter2 "completed" directly, without going through the router
    # (so no finalize check ever runs for it) — leaving the submission at
    # "pending" even though both submitters are now "completed".
    submitter2 = db.get(Submitter, submitter2_id)
    submitter2.status = "completed"
    db.commit()

    stranded = admin_client.get(f"/api/submissions/{submission['id']}")
    assert stranded.json()["status"] == "pending"  # confirms the stranded state was actually created

    heal_resp = user_client.post(f"/api/sign/{submitter1_id}/complete", json={"values": {"sig1": sig1_id}})
    assert heal_resp.status_code == 200
    assert heal_resp.json() == {"already": True}

    healed = admin_client.get(f"/api/submissions/{submission['id']}")
    body = healed.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None

    completed_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "completed"),
    ).all()
    assert len(completed_events) == 1
    assert completed_events[0].actor_user_id is None


# --- PDF stamping + completion pipeline (Task 7) -----------------------------


def _two_signer_submission(
    admin_client: TestClient,
    signer1: TestClient,
    signer2: TestClient,
    *,
    title: str = "Stamp Test",
) -> tuple[dict, int, int]:
    """Create a two-signature-field submission for signer1/signer2; return (submission, submitter1_id, submitter2_id)."""
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("sig2", "signature", "Signer 2", x=0.5),
    ]
    template_id = _upload_template(admin_client, fields, name=title)
    signer1_id = _me_id(signer1)
    signer2_id = _me_id(signer2)
    submission = _create_submission(
        admin_client,
        template_id,
        [{"role": "Signer 1", "user_id": signer1_id}, {"role": "Signer 2", "user_id": signer2_id}],
        title=title,
    )
    submitter1_id = _submitter_id_for(submission, signer1_id)
    submitter2_id = _submitter_id_for(submission, signer2_id)
    return submission, submitter1_id, submitter2_id


def _complete_with_signature(client: TestClient, submitter_id: int, field_id: str) -> None:
    sig_resp = client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})
    assert sig_resp.status_code == 200, sig_resp.text
    sig_id = sig_resp.json()["signature_id"]
    complete_resp = client.post(f"/api/sign/{submitter_id}/complete", json={"values": {field_id: sig_id}})
    assert complete_resp.status_code == 200, complete_resp.text


def test_complete_last_signer_stamps_and_saves_signed_pdf(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    signer2 = _login(make_client, app_settings, "signer2-stamp@pumasi.ai", "Signer Two")
    submission, submitter1_id, submitter2_id = _two_signer_submission(admin_client, user_client, signer2)

    _complete_with_signature(user_client, submitter1_id, "sig1")
    _complete_with_signature(signer2, submitter2_id, "sig2")

    sub = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert sub["status"] == "completed"
    assert sub["completed_at"] is not None

    db_submission = db.get(Submission, submission["id"])
    assert db_submission.signed_pdf_key == f"submissions/{submission['id']}/signed.pdf"
    assert db_submission.certificate_pdf_key == f"submissions/{submission['id']}/certificate.pdf"
    assert sub["has_certificate"] is True

    pdf_resp = admin_client.get(f"/api/files/signed-pdf/{submission['id']}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")

    # The certificate is its own artifact, no longer appended to the signed PDF.
    signed_reader = PdfReader(io.BytesIO(pdf_resp.content))
    assert all("Signature Certificate" not in page.extract_text() for page in signed_reader.pages)

    cert_resp = admin_client.get(f"/api/files/certificate/{submission['id']}")
    assert cert_resp.status_code == 200
    assert cert_resp.headers["content-type"] == "application/pdf"
    cert_reader = PdfReader(io.BytesIO(cert_resp.content))
    assert "Signature Certificate" in cert_reader.pages[0].extract_text()


def test_get_signed_pdf_unrelated_admin_is_403(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    """Regression test for a deliberate product decision (see ``files.py``'s
    module docstring: "Deliberately not 'admins' too — matches the brief
    literally"): the signed-pdf file route grants access only to a
    submission's sender or its submitters, *not* to admins in general.
    Without this test, a future refactor of ``get_signed_pdf`` (e.g. someone
    "helpfully" adding an ``or user.is_admin`` bypass, matching the pattern
    used by the template-pdf and signature-image routes) could silently
    widen access to every signed document company-wide with no test
    catching it.
    """
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    _complete_with_signature(user_client, submitter_id, "sig1")

    sub = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert sub["status"] == "completed"

    # An admin who is neither this submission's sender nor one of its
    # submitters. Inserted directly (is_admin=True) rather than via
    # ADMIN_EMAILS, then dev-logged-in — `upsert_user` never demotes an
    # already-admin user, so this stays admin without needing a second
    # entry in app_settings.admin_emails.
    other_admin = User(email="other-admin@pumasi.ai", name="Other Admin", is_admin=True)
    db.add(other_admin)
    db.commit()
    other_admin_client = _login(make_client, app_settings, "other-admin@pumasi.ai", "Other Admin")

    response = other_admin_client.get(f"/api/files/signed-pdf/{submission['id']}")

    assert response.status_code == 403

    # The certificate route follows the same access rule.
    cert_response = other_admin_client.get(f"/api/files/certificate/{submission['id']}")
    assert cert_response.status_code == 403


def test_completion_email_sent_after_commit_not_from_inside_finalize(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: ``completion.finalize`` must not send the completion
    email itself — it runs under ``finalize_if_ready``'s ``SELECT ... FOR
    UPDATE`` lock, so a slow/hung Graph send there would hold the lock for
    as long as the send takes (worst case ~2 minutes across Graph's retry
    backoff). The email must be sent by the router only *after* its own
    ``db.commit()`` releases that lock.

    Verified two ways: (1) by the time ``completion.finalize`` returns
    (i.e. from inside the still-locked transaction), ``mailer.send`` must
    not have been called yet; (2) by the time the whole ``/complete``
    request (including its commit) has returned, it must have been called
    exactly once.
    """
    signer2 = _login(make_client, app_settings, "signer2-email-order@pumasi.ai", "Signer Two")
    submission, submitter1_id, submitter2_id = _two_signer_submission(
        admin_client,
        user_client,
        signer2,
        title="Email Order Test",
    )

    send_calls: list[list[str]] = []

    def fake_send(settings, to, subject, html_body, attachments=None):
        send_calls.append(to)
        return True

    monkeypatch.setattr(notifications.mailer, "send", fake_send)

    real_finalize = completion.finalize
    calls_seen_during_finalize: list[list[list[str]]] = []

    def spy_finalize(db, submission_id, storage):
        real_finalize(db, submission_id, storage)
        # Still inside finalize() here — under the row lock, before the
        # router's commit. No email should have gone out yet.
        calls_seen_during_finalize.append(list(send_calls))

    monkeypatch.setattr(completion, "finalize", spy_finalize)

    _complete_with_signature(user_client, submitter1_id, "sig1")
    _complete_with_signature(signer2, submitter2_id, "sig2")

    assert calls_seen_during_finalize == [[]]
    assert len(send_calls) == 1


def test_completion_triggers_sharepoint_archive(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import sharepoint

    archived_ids: list[int] = []

    def fake_archive(db: object, submission: object, storage: object, settings: object) -> bool:
        archived_ids.append(submission.id)  # type: ignore[attr-defined]
        return True

    monkeypatch.setattr(sharepoint, "archive_submission", fake_archive)

    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    _complete_with_signature(user_client, submitter_id, "sig1")

    assert archived_ids == [submission["id"]]


def test_archive_failure_does_not_affect_completion(
    admin_client: TestClient,
    user_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import sharepoint

    monkeypatch.setattr(sharepoint, "archive_submission", lambda db, submission, storage, settings: False)

    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    _complete_with_signature(user_client, submitter_id, "sig1")

    detail = admin_client.get(f"/api/submissions/{submission['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "completed"


def test_cancel_after_completion_is_409_sequential_case(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """Sequential-only regression test for the cancel-vs-last-complete race:
    once a submission has actually completed (signed PDF built, "completed"
    audit event written) and that transaction has fully committed, a
    *subsequent, non-overlapping* cancel call must 409 and must NOT append a
    "cancelled" audit event after it.

    This does **not** exercise the identity-map-staleness bug the lock's
    ``populate_existing=True`` fixes (both requests here run one after the
    other, each starting with a brand-new, uncached session, so there's no
    stale cached object for either to read) — it only proves the plain
    status check still behaves correctly in the easy, non-racing case. The
    actual overlapping-transaction race — including the specific
    identity-map staleness bug — is reproduced with real concurrent
    transactions in ``test_cancel_locked_select_refreshes_stale_status``
    below.
    """
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    _complete_with_signature(user_client, submitter_id, "sig1")

    sub = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert sub["status"] == "completed"

    resp = admin_client.post(f"/api/submissions/{submission['id']}/cancel")
    assert resp.status_code == 409

    events = db.scalars(
        select(AuditEvent.event).where(AuditEvent.submission_id == submission["id"]).order_by(AuditEvent.id),
    ).all()
    assert events[-1] == "completed"
    assert "cancelled" not in events


def test_cancel_locked_select_refreshes_stale_status(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """Real concurrency regression test for identity-map staleness in
    ``cancel_submission``'s locked re-check (``routers/submissions.py``).

    ``cancel_submission`` does an unlocked ``db.get`` "precheck" (for the
    404/403 checks), which loads the ``Submission`` into *that request's
    own session's* identity map. It then takes a ``SELECT ... FOR UPDATE``
    lock on the same row and re-checks ``status``. Without
    ``execution_options(populate_existing=True)`` on that locked select,
    SQLAlchemy returns the *same* already-cached Python object as-is rather
    than overwriting its attributes with the row the lock just read — so
    the status check would silently read the value cached *before* the
    lock blocked and unblocked, not the value the lock made current. That
    is exactly what would let a cancel request "win" against a completion
    that actually committed first.

    Reproduced with two real, overlapping transactions — a background
    thread is required (not just two ``Session`` objects), because the
    whole point under test is that the cancel request's ``FOR UPDATE``
    call must genuinely *block* on another transaction's uncommitted lock
    and then observe what that transaction committed:

    1. A background thread opens an independent connection/session,
       ``UPDATE``s the submission row to ``"completed"`` *without
       committing*, signals readiness, sleeps briefly (long enough that the
       cancel call below is genuinely blocked on the row lock), then
       commits and closes.
    2. Once the background thread signals its (uncommitted) update is in
       place, this test calls ``POST /api/submissions/{id}/cancel``.
       Inside that request's own (separate, freshly-created) session, the
       unlocked precheck runs *before* the background thread commits, so
       under READ COMMITTED it sees the last-committed value ("pending") —
       populating that request's identity map with the stale value, same
       as production. The subsequent locked select then blocks until the
       background thread commits.
    3. The cancel request must come back 409 (not 200) once unblocked, and
       the row must still read "completed" afterward — not "cancelled".

    Against the pre-fix code (locked select without ``populate_existing``),
    this test fails: the cancel request incorrectly succeeds (200) and
    overwrites the already-completed submission's status to "cancelled".
    """
    submission, _submitter_id = _single_signer_submission(admin_client, user_client)
    submission_id = submission["id"]

    blocker_engine = create_engine(TEST_DATABASE_URL)
    blocker = sessionmaker(bind=blocker_engine)()
    lock_acquired = threading.Event()

    def hold_uncommitted_completion() -> None:
        blocker.execute(
            text("UPDATE submissions SET status = 'completed' WHERE id = :id"),
            {"id": submission_id},
        )
        lock_acquired.set()
        time.sleep(0.5)
        blocker.commit()
        blocker.close()

    thread = threading.Thread(target=hold_uncommitted_completion)
    thread.start()
    try:
        assert lock_acquired.wait(timeout=5), "blocker thread never acquired the row lock"

        response = admin_client.post(f"/api/submissions/{submission_id}/cancel")
    finally:
        thread.join(timeout=5)
        blocker_engine.dispose()

    assert response.status_code == 409, response.text

    row_status = db.scalar(select(Submission.status).where(Submission.id == submission_id))
    assert row_status == "completed"


def test_finalize_if_ready_locked_select_refreshes_stale_status(
    admin_client: TestClient,
    user_client: TestClient,
    app_settings: Settings,
    db: Session,
) -> None:
    """Real concurrency regression test for the same identity-map staleness
    bug class in ``completion.finalize_if_ready`` itself (the reviewer's
    flagged concern: its callers — ``complete_signing`` via
    ``submitter.submission``, ``retry_completion`` via ``db.get`` — always
    load the ``Submission`` into their session *before* calling here, so
    its own locked select needs ``populate_existing=True`` just as much as
    ``cancel_submission``'s does).

    Setup mirrors ``test_cancel_locked_select_refreshes_stale_status``:
    this test's own ``db`` session loads the submission (status "pending")
    first — simulating an already-cached caller — then a background thread
    holds an uncommitted ``UPDATE ... SET status = 'completed'`` on the
    same row while this test calls ``completion.finalize_if_ready`` on that
    same (already-cached) session. The call must block on the thread's
    uncommitted lock, then correctly observe "completed" once it commits —
    returning ``NOT_PENDING`` — rather than trusting the stale "pending"
    it had cached before ever calling in.

    Against the pre-fix code (no ``populate_existing`` on the locked
    select), this test fails: the call proceeds past the stale "pending"
    check and (since the submitter here is already "completed") re-invokes
    ``finalize`` on a submission that a concurrent transaction just
    completed — the exact double-finalize the lock exists to prevent.
    """
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    submission_id = submission["id"]

    # Mark the submitter completed directly (bypassing the router, as
    # test_complete_self_heals_a_stranded_submission also does) so
    # finalize_if_ready's "is everyone done?" check passes — the
    # submission's own status is deliberately left "pending" here; the
    # background thread below flips it to "completed" via an uncommitted,
    # concurrent transaction instead.
    submitter = db.get(Submitter, submitter_id)
    submitter.status = "completed"
    db.commit()

    # Caller-simulation: load the Submission into *this* session's identity
    # map before the background thread's update exists at all — exactly
    # what complete_signing/retry_completion already did in production
    # before ever calling finalize_if_ready.
    cached = db.get(Submission, submission_id)
    assert cached.status == "pending"

    blocker_engine = create_engine(TEST_DATABASE_URL)
    blocker = sessionmaker(bind=blocker_engine)()
    lock_acquired = threading.Event()

    def hold_uncommitted_completion() -> None:
        blocker.execute(
            text("UPDATE submissions SET status = 'completed' WHERE id = :id"),
            {"id": submission_id},
        )
        lock_acquired.set()
        time.sleep(0.5)
        blocker.commit()
        blocker.close()

    thread = threading.Thread(target=hold_uncommitted_completion)
    thread.start()
    try:
        assert lock_acquired.wait(timeout=5), "blocker thread never acquired the row lock"

        storage = get_storage(app_settings)
        outcome = completion.finalize_if_ready(db, submission_id, storage)
    finally:
        thread.join(timeout=5)
        blocker_engine.dispose()

    assert outcome == completion.FinalizeOutcome.NOT_PENDING


def test_complete_guards_against_concurrent_replace(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    """Real concurrency regression test: ``replace_submitter`` committing
    mid-flight of a ``/complete`` request must not let that request
    attribute its payload to whoever replaced the original signer.

    ``complete_signing`` used to mutate the submitter it loaded via the
    unlocked ``_get_submitter_authorized`` call without ever re-checking
    that row under a lock — unlike ``decline_signing``/``cancel_submission``,
    which both take the submission's ``SELECT ... FOR UPDATE`` first. A
    ``replace_submitter`` call also takes that same submission-row lock
    before touching the submitter, so the fix is to take it here too:
    doing so serializes the two, and a populate_existing re-read of the
    submitter afterward reveals the swap.

    Reproduced with two real, overlapping transactions, mirroring
    ``test_finalize_if_ready_locked_select_refreshes_stale_status``:

    1. A background thread opens its own connection, takes the submission's
       ``FOR UPDATE`` lock, ``UPDATE``s the submitter's ``user_id`` (and
       resets its ``status`` to "pending", exactly what ``replace_submitter``
       does) *without committing*, signals readiness, sleeps briefly, then
       commits and closes — atomically making the swap visible at the same
       moment the lock releases, just like the real route.
    2. Once the background thread signals its (uncommitted) update is in
       place, this test calls the original signer's ``/complete``. Its
       unlocked authorization read runs before the background thread
       commits, so it captures the *old* user_id — same as a real request
       racing a real concurrent replace. The subsequent locked select then
       blocks until the background thread commits.
    3. The ``/complete`` call must come back 409 (not 200), and the
       submitter row must still show the new user_id and a non-"completed"
       status afterward — not the old signer's values.

    Against the pre-fix code (no lock, no re-check), this test fails: the
    request proceeds past the stale (pre-swap) submitter object it already
    had in memory and marks it "completed" under the wrong identity.
    """
    signer2 = _login(make_client, app_settings, "signer2-race@pumasi.ai", "Signer Two")
    submission, submitter_id = _single_signer_submission(admin_client, user_client)
    submission_id = submission["id"]
    new_user_id = _me_id(signer2)

    # A real signature owned by the original (about-to-be-replaced) signer,
    # obtained before the race — so the request that follows carries a
    # payload that would pass field validation if it were (wrongly) still
    # treated as that signer's completion.
    sig_id = user_client.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL}).json()["signature_id"]

    blocker_engine = create_engine(TEST_DATABASE_URL)
    blocker = sessionmaker(bind=blocker_engine)()
    lock_acquired = threading.Event()

    def hold_uncommitted_replace() -> None:
        blocker.execute(text("SELECT id FROM submissions WHERE id = :id FOR UPDATE"), {"id": submission_id})
        blocker.execute(
            text("UPDATE submitters SET user_id = :uid, status = 'pending' WHERE id = :id"),
            {"uid": new_user_id, "id": submitter_id},
        )
        lock_acquired.set()
        time.sleep(0.5)
        blocker.commit()
        blocker.close()

    thread = threading.Thread(target=hold_uncommitted_replace)
    thread.start()
    try:
        assert lock_acquired.wait(timeout=5), "blocker thread never acquired the row lock"

        response = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig_id}})
    finally:
        thread.join(timeout=5)
        blocker_engine.dispose()

    assert response.status_code == 409, response.text

    row = db.execute(
        select(Submitter.user_id, Submitter.status).where(Submitter.id == submitter_id),
    ).one()
    assert row.user_id == new_user_id
    assert row.status != "completed"


def test_stamping_failure_leaves_pending_then_retry_completion_succeeds(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signer2 = _login(make_client, app_settings, "signer2-fail@pumasi.ai", "Signer Two")
    submission, submitter1_id, submitter2_id = _two_signer_submission(
        admin_client,
        user_client,
        signer2,
        title="Stamp Fail Test",
    )

    def _boom(*_args: object, **_kwargs: object) -> bytes:
        raise RuntimeError("stamping exploded")

    with monkeypatch.context() as mp:
        mp.setattr("app.completion.build_signed_pdf", _boom)
        _complete_with_signature(user_client, submitter1_id, "sig1")
        # The last signer's /complete must still succeed even though stamping failed.
        _complete_with_signature(signer2, submitter2_id, "sig2")

    stuck = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert stuck["status"] == "pending"
    assert stuck["completed_at"] is None

    db_submission = db.get(Submission, submission["id"])
    assert db_submission.signed_pdf_key is None
    completed_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "completed"),
    ).all()
    assert completed_events == []

    retry_resp = admin_client.post(f"/api/submissions/{submission['id']}/retry-completion")
    assert retry_resp.status_code == 200, retry_resp.text
    body = retry_resp.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None

    db.refresh(db_submission)
    assert db_submission.signed_pdf_key == f"submissions/{submission['id']}/signed.pdf"

    pdf_resp = admin_client.get(f"/api/files/signed-pdf/{submission['id']}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")


def test_retry_completion_after_success_is_409_and_does_not_duplicate_audit_event(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: a second, sequential retry-completion after the first one already
    succeeded must not re-run finalize (no duplicate "completed" audit
    event, no double stamping).

    The route's status pre-check alone catches this sequential case
    (status is no longer "pending" after the first retry succeeds), and
    ``completion.finalize_if_ready``'s row-locked check is the same guard
    that would also catch a *concurrent* second retry (harder to exercise
    here — see ``test_complete_self_heals_a_stranded_submission`` for why
    true interleaving isn't practical against a synchronous TestClient —
    but this at least proves the sequential/state-based half of the guard).
    """
    signer2 = _login(make_client, app_settings, "signer2-retry-twice@pumasi.ai", "Signer Two")
    submission, submitter1_id, submitter2_id = _two_signer_submission(
        admin_client,
        user_client,
        signer2,
        title="Retry Twice Test",
    )

    def _boom(*_args: object, **_kwargs: object) -> bytes:
        raise RuntimeError("stamping exploded")

    with monkeypatch.context() as mp:
        mp.setattr("app.completion.build_signed_pdf", _boom)
        _complete_with_signature(user_client, submitter1_id, "sig1")
        _complete_with_signature(signer2, submitter2_id, "sig2")

    first_retry = admin_client.post(f"/api/submissions/{submission['id']}/retry-completion")
    assert first_retry.status_code == 200, first_retry.text
    assert first_retry.json()["status"] == "completed"

    second_retry = admin_client.post(f"/api/submissions/{submission['id']}/retry-completion")
    assert second_retry.status_code == 409

    completed_events = db.scalars(
        select(AuditEvent).where(AuditEvent.submission_id == submission["id"], AuditEvent.event == "completed"),
    ).all()
    assert len(completed_events) == 1


# --- POST /api/submissions/{id}/retry-completion -----------------------------


def test_retry_completion_unknown_submission_is_404(admin_client: TestClient) -> None:
    response = admin_client.post("/api/submissions/999999/retry-completion")

    assert response.status_code == 404


def test_retry_completion_forbidden_for_non_sender_non_admin(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    bystander = _login(make_client, app_settings, "retry-bystander@pumasi.ai", "Bystander")
    submission, _submitter_id = _single_signer_submission(admin_client, user_client)

    response = bystander.post(f"/api/submissions/{submission['id']}/retry-completion")

    assert response.status_code == 403


def test_retry_completion_not_all_completed_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    submission, _submitter_id = _single_signer_submission(admin_client, user_client)

    response = admin_client.post(f"/api/submissions/{submission['id']}/retry-completion")

    assert response.status_code == 409


def test_retry_completion_on_cancelled_submission_is_409(admin_client: TestClient, user_client: TestClient) -> None:
    submission, _submitter_id = _single_signer_submission(admin_client, user_client)
    admin_client.post(f"/api/submissions/{submission['id']}/cancel")

    response = admin_client.post(f"/api/submissions/{submission['id']}/retry-completion")

    assert response.status_code == 409


# --- review fixes: CC-aware retry, turn-aware decline/open, role_names -------


def test_retry_completion_succeeds_with_cc_recipient(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CC rows stay status="pending" forever; retry-completion must ignore
    them like finalize_if_ready does, or stuck CC envelopes are unrecoverable."""
    cc_client = _login(make_client, app_settings, "cc-retry@pumasi.ai", "CC Retry")
    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    submission = _create_submission(
        admin_client,
        template_id,
        [
            {"role": "Signer 1", "user_id": _me_id(user_client)},
            {"user_id": _me_id(cc_client), "is_cc": True},
        ],
    )
    submitter_id = _submitter_id_for(submission, _me_id(user_client))

    def _boom(*_args: object, **_kwargs: object) -> bytes:
        raise RuntimeError("stamping exploded")

    with monkeypatch.context() as mp:
        mp.setattr("app.completion.build_signed_pdf", _boom)
        _complete_with_signature(user_client, submitter_id, "sig1")

    assert admin_client.get(f"/api/submissions/{submission['id']}").json()["status"] == "pending"

    retry = admin_client.post(f"/api/submissions/{submission['id']}/retry-completion")
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "completed"


def _ordered_two_signer_submission(
    admin_client: TestClient,
    first_client: TestClient,
    second_client: TestClient,
) -> tuple[dict, int, int]:
    fields = [
        _field("sig1", "signature", "Signer 1"),
        _field("sig2", "signature", "Signer 2", x=0.5),
    ]
    template_id = _upload_template(admin_client, fields)
    submission = _create_submission(
        admin_client,
        template_id,
        [
            {"role": "Signer 1", "user_id": _me_id(first_client), "order": 0},
            {"role": "Signer 2", "user_id": _me_id(second_client), "order": 1},
        ],
    )
    return (
        submission,
        _submitter_id_for(submission, _me_id(first_client)),
        _submitter_id_for(submission, _me_id(second_client)),
    )


def test_decline_out_of_turn_is_409(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    """Declining voids the whole envelope, so it obeys the same turn rule as
    /complete — a group-2 signer can't kill the envelope before group 1 acts."""
    second_client = _login(make_client, app_settings, "decline-order@pumasi.ai", "Second Signer")
    submission, first_submitter, second_submitter = _ordered_two_signer_submission(
        admin_client,
        user_client,
        second_client,
    )

    blocked = second_client.post(f"/api/sign/{second_submitter}/decline", json={"reason": "too early"})
    assert blocked.status_code == 409

    assert admin_client.get(f"/api/submissions/{submission['id']}").json()["status"] == "pending"

    _complete_with_signature(user_client, first_submitter, "sig1")

    allowed = second_client.post(f"/api/sign/{second_submitter}/decline", json={"reason": "changed my mind"})
    assert allowed.status_code == 200, allowed.text
    assert admin_client.get(f"/api/submissions/{submission['id']}").json()["status"] == "declined"


def test_get_sign_view_does_not_flip_opened_before_turn(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
    db: Session,
) -> None:
    """Peeking at a not-yet-routed envelope is not an "opened" — the audit
    trail (and certificate) must not show opens predating the sign request."""
    second_client = _login(make_client, app_settings, "peek-order@pumasi.ai", "Second Signer")
    _submission, first_submitter, second_submitter = _ordered_two_signer_submission(
        admin_client,
        user_client,
        second_client,
    )

    view = second_client.get(f"/api/sign/{second_submitter}")
    assert view.status_code == 200
    assert view.json()["my_turn"] is False

    row = db.get(Submitter, second_submitter)
    db.refresh(row)
    assert row.status == "pending"
    # Nobody has legitimately opened yet (signer 1 never viewed), so the
    # premature peek must have produced zero "opened" events.
    opened_events = db.scalars(
        select(AuditEvent).where(
            AuditEvent.submission_id == row.submission_id,
            AuditEvent.event == "opened",
        ),
    ).all()
    assert opened_events == []

    # Once it's their turn, the first view flips them to opened as before.
    _complete_with_signature(user_client, first_submitter, "sig1")
    second_client.get(f"/api/sign/{second_submitter}")
    db.refresh(row)
    assert row.status == "opened"


def test_role_names_exclude_cc_recipients(
    admin_client: TestClient,
    user_client: TestClient,
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    cc_client = _login(make_client, app_settings, "cc-names@pumasi.ai", "CC Viewer")
    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    submission = _create_submission(
        admin_client,
        template_id,
        [
            {"role": "Signer 1", "user_id": _me_id(user_client)},
            {"user_id": _me_id(cc_client), "is_cc": True},
        ],
    )
    submitter_id = _submitter_id_for(submission, _me_id(user_client))

    view = user_client.get(f"/api/sign/{submitter_id}").json()
    assert "" not in view["role_names"]
    assert "CC Viewer" not in view["role_names"].values()
