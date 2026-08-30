"""Dropdown/radio choice fields, signer attachment uploads, and text
validation formats — schema rules, signing-time validation, and the
attachment pages appended to the completed PDF."""

import io
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.storage import get_storage

from .test_signing import (
    PNG_DATA_URL,
    _create_submission,
    _field,
    _me_id,
    _submitter_id_for,
    _upload_template,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _choice_field(field_id: str, field_type: str, role: str, options: list[str] | None) -> dict:
    field = _field(field_id, field_type, role)
    if options is not None:
        field["options"] = options
    return field


# --- FieldDef schema rules ---------------------------------------------------


def test_dropdown_without_options_is_422(admin_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    resp = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": [_choice_field("dd", "dropdown", "Signer 1", None)]},
    )
    assert resp.status_code == 422


def test_dropdown_with_empty_or_duplicate_options_is_422(admin_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    for options in ([], ["a", "a"], ["  "]):
        resp = admin_client.put(
            f"/api/templates/{template_id}/fields",
            json={"fields": [_choice_field("dd", "dropdown", "Signer 1", options)]},
        )
        assert resp.status_code == 422, options


def test_options_normalized_away_on_non_choice_types(admin_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    field = _field("t1", "text", "Signer 1")
    field["options"] = ["a", "b"]
    resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [field]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["fields"][0]["options"] is None


def test_validation_only_survives_on_text_fields(admin_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    text_field = _field("t1", "text", "Signer 1")
    text_field["validation"] = "email"
    date_field = _field("d1", "date", "Signer 1", x=0.4)
    date_field["validation"] = "email"
    resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [text_field, date_field]})
    assert resp.status_code == 200, resp.text
    by_id = {f["id"]: f for f in resp.json()["fields"]}
    assert by_id["t1"]["validation"] == "email"
    assert by_id["d1"]["validation"] is None


# --- signing-time value validation ------------------------------------------


def _one_field_submission(
    admin_client: TestClient,
    signer_client: TestClient,
    field: dict,
) -> tuple[dict, int]:
    template_id = _upload_template(admin_client, [field])
    signer_id = _me_id(signer_client)
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": signer_id}])
    return submission, _submitter_id_for(submission, signer_id)


def test_dropdown_value_must_be_an_option(admin_client: TestClient, user_client: TestClient) -> None:
    field = _choice_field("dd", "dropdown", "Signer 1", ["Alpha", "Beta"])
    _, submitter_id = _one_field_submission(admin_client, user_client, field)

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"dd": "Gamma"}})
    assert resp.status_code == 422

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"dd": "Beta"}})
    assert resp.status_code == 200, resp.text


def test_radio_value_must_be_an_option(admin_client: TestClient, user_client: TestClient) -> None:
    field = _choice_field("r1", "radio", "Signer 1", ["Yes", "No"])
    _, submitter_id = _one_field_submission(admin_client, user_client, field)

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"r1": True}})
    assert resp.status_code == 422

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"r1": "Yes"}})
    assert resp.status_code == 200, resp.text


def test_text_email_validation(admin_client: TestClient, user_client: TestClient) -> None:
    field = _field("t1", "text", "Signer 1")
    field["validation"] = "email"
    _, submitter_id = _one_field_submission(admin_client, user_client, field)

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"t1": "not-an-email"}})
    assert resp.status_code == 422

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"t1": "a@b.com"}})
    assert resp.status_code == 200, resp.text


def test_text_number_validation(admin_client: TestClient, user_client: TestClient) -> None:
    field = _field("t1", "text", "Signer 1")
    field["validation"] = "number"
    _, submitter_id = _one_field_submission(admin_client, user_client, field)

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"t1": "12abc"}})
    assert resp.status_code == 422

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"t1": "-12.5"}})
    assert resp.status_code == 200, resp.text


# --- attachment upload + completion ------------------------------------------


def test_attachment_roundtrip_appends_pages_to_signed_pdf(
    admin_client: TestClient,
    user_client: TestClient,
    app_settings,
) -> None:
    field = _field("att", "attachment", "Signer 1")
    submission, submitter_id = _one_field_submission(admin_client, user_client, field)

    attachment_pdf = (FIXTURES / "sample.pdf").read_bytes()
    resp = user_client.post(
        f"/api/sign/{submitter_id}/attachment",
        files={"file": ("proof.pdf", attachment_pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    attachment_id = resp.json()["attachment_id"]
    assert resp.json()["filename"] == "proof.pdf"

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"att": attachment_id}})
    assert resp.status_code == 200, resp.text

    storage = get_storage(app_settings)
    signed = storage.open(f"submissions/{submission['id']}/signed.pdf")
    template_pages = len(PdfReader(io.BytesIO((FIXTURES / "sample.pdf").read_bytes())).pages)
    signed_pages = len(PdfReader(io.BytesIO(signed)).pages)
    assert signed_pages == template_pages + template_pages  # doc + appended attachment (same fixture)


def test_attachment_image_becomes_a_page(
    admin_client: TestClient,
    user_client: TestClient,
    app_settings,
) -> None:
    field = _field("att", "attachment", "Signer 1")
    submission, submitter_id = _one_field_submission(admin_client, user_client, field)

    png_bytes = __import__("base64").b64decode(PNG_DATA_URL.split(",", 1)[1])
    resp = user_client.post(
        f"/api/sign/{submitter_id}/attachment",
        files={"file": ("photo.png", png_bytes, "image/png")},
    )
    assert resp.status_code == 200, resp.text
    attachment_id = resp.json()["attachment_id"]

    resp = user_client.post(f"/api/sign/{submitter_id}/complete", json={"values": {"att": attachment_id}})
    assert resp.status_code == 200, resp.text

    storage = get_storage(app_settings)
    signed = storage.open(f"submissions/{submission['id']}/signed.pdf")
    template_pages = len(PdfReader(io.BytesIO((FIXTURES / "sample.pdf").read_bytes())).pages)
    assert len(PdfReader(io.BytesIO(signed)).pages) == template_pages + 1


def test_attachment_upload_rejects_unsupported_bytes(admin_client: TestClient, user_client: TestClient) -> None:
    field = _field("att", "attachment", "Signer 1")
    _, submitter_id = _one_field_submission(admin_client, user_client, field)
    resp = user_client.post(
        f"/api/sign/{submitter_id}/attachment",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert resp.status_code == 422


def test_attachment_upload_rejects_oversize(admin_client: TestClient, user_client: TestClient) -> None:
    field = _field("att", "attachment", "Signer 1")
    _, submitter_id = _one_field_submission(admin_client, user_client, field)
    big = b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 1)
    resp = user_client.post(
        f"/api/sign/{submitter_id}/attachment",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert resp.status_code == 413


def test_attachment_must_belong_to_this_submitter(admin_client: TestClient, user_client: TestClient) -> None:
    field = _field("att", "attachment", "Signer 1")
    _, first_submitter = _one_field_submission(admin_client, user_client, field)
    _, second_submitter = _one_field_submission(admin_client, user_client, field)

    attachment_pdf = (FIXTURES / "sample.pdf").read_bytes()
    resp = user_client.post(
        f"/api/sign/{first_submitter}/attachment",
        files={"file": ("proof.pdf", attachment_pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    attachment_id = resp.json()["attachment_id"]

    # Same user, but the attachment was uploaded under a different submitter
    # row — using it on another envelope is rejected.
    resp = user_client.post(f"/api/sign/{second_submitter}/complete", json={"values": {"att": attachment_id}})
    assert resp.status_code == 422
