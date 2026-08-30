"""Tests for the templates API and authorized file serving.

``admin_client``/``user_client`` (from conftest) share one ``app_settings``
instance per test, so they hit the same test database and the same
temp-dir file storage — letting a test create a template as admin and then
assert what a plain user can/can't fetch.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Signature, Submission, Submitter, User
from app.storage import get_storage

FIXTURES = Path(__file__).parent / "fixtures"


def _upload(client: TestClient, *, name: str = "My Template", filename: str = "sample.pdf", data: bytes | None = None):
    if data is None:
        data = (FIXTURES / filename).read_bytes()
    return client.post(
        "/api/templates",
        data={"name": name},
        files={"file": (filename, data, "application/octet-stream")},
    )


# --- create -----------------------------------------------------------------


def test_create_template_allowed_for_non_admin_sender(user_client: TestClient) -> None:
    """A plain internal user with the default ``can_send=True`` may create templates."""
    response = _upload(user_client)

    assert response.status_code == 201


def test_revoked_user_cannot_create_template(user_client: TestClient, db: Session) -> None:
    user_id = user_client.get("/api/auth/me").json()["id"]
    user = db.get(User, user_id)
    user.can_send = False
    db.commit()

    response = _upload(user_client)

    assert response.status_code == 403


def test_create_template_pdf_creates_row_with_page_count(admin_client: TestClient) -> None:
    response = _upload(admin_client)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My Template"
    assert body["page_count"] == 2
    assert body["fields"] == []
    assert "id" in body
    assert "created_at" in body


def test_create_template_bad_magic_bytes_returns_422(admin_client: TestClient) -> None:
    response = _upload(admin_client, filename="sample.pdf", data=b"this is not a pdf at all")

    assert response.status_code == 422
    assert response.json()["detail"]


def test_create_template_unsupported_extension_returns_422(admin_client: TestClient) -> None:
    response = _upload(admin_client, filename="sample.exe", data=b"MZ binary")

    assert response.status_code == 422
    assert response.json()["detail"]


def test_create_template_encrypted_pdf_returns_422(admin_client: TestClient) -> None:
    response = _upload(admin_client, filename="sample-encrypted.pdf")

    assert response.status_code == 422


def test_create_template_oversized_file_returns_413(admin_client: TestClient) -> None:
    oversized = b"%PDF-1.4\n" + (b"0" * (25 * 1024 * 1024 + 1))

    response = _upload(admin_client, filename="huge.pdf", data=oversized)

    assert response.status_code == 413


def test_create_template_failed_conversion_does_not_persist_row(admin_client: TestClient) -> None:
    _upload(admin_client, filename="sample.pdf", data=b"garbage")

    listing = admin_client.get("/api/templates")
    assert listing.json() == []


# --- fields -------------------------------------------------------------


def test_update_fields_allowed_for_non_admin_sender(user_client: TestClient) -> None:
    template_id = _upload(user_client).json()["id"]

    response = user_client.put(f"/api/templates/{template_id}/fields", json={"fields": []})

    assert response.status_code == 200


def test_update_fields_persists_valid_fields(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]
    field = {
        "id": "f1",
        "type": "signature",
        "role": "Signer 1",
        "page": 0,
        "x": 0.1,
        "y": 0.1,
        "w": 0.2,
        "h": 0.05,
        "required": True,
    }

    response = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [field]})

    # Round-trips with the schema's optional extras (None when unset).
    expected = {**field, "default_value": None, "font_size": None, "options": None, "validation": None}
    assert response.status_code == 200
    assert response.json()["fields"] == [expected]

    fetched = admin_client.get(f"/api/templates/{template_id}")
    assert fetched.json()["fields"] == [expected]


def test_update_fields_accepts_font_size_and_rejects_out_of_range(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    def field(font_size):
        return {
            "id": "f1",
            "type": "text",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": False,
            "font_size": font_size,
        }

    ok = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [field(24)]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["fields"][0]["font_size"] == 24

    for bad in (5, 73, -1):
        resp = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [field(bad)]})
        assert resp.status_code == 422, f"font_size={bad}: {resp.status_code}"


def test_update_fields_rejects_geometry_exceeding_bounds(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]
    field = {
        "id": "f1",
        "type": "text",
        "role": "Signer 1",
        "page": 0,
        "x": 0.9,
        "y": 0.1,
        "w": 0.2,
        "h": 0.05,
        "required": False,
    }

    response = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [field]})

    assert response.status_code == 422


def test_update_fields_rejects_page_out_of_range(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]  # sample.pdf has 2 pages: 0, 1
    field = {
        "id": "f1",
        "type": "text",
        "role": "Signer 1",
        "page": 5,
        "x": 0.1,
        "y": 0.1,
        "w": 0.2,
        "h": 0.05,
        "required": False,
    }

    response = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": [field]})

    assert response.status_code == 422
    assert response.json()["detail"] == "page out of range"


def test_update_fields_404_for_missing_template(admin_client: TestClient) -> None:
    response = admin_client.put("/api/templates/999999/fields", json={"fields": []})

    assert response.status_code == 404


# --- roles ---------------------------------------------------------------


def _field(role: str, field_id: str = "f1") -> dict:
    return {
        "id": field_id,
        "type": "signature",
        "role": role,
        "page": 0,
        "x": 0.1,
        "y": 0.1,
        "w": 0.2,
        "h": 0.05,
        "required": True,
    }


def test_create_template_starts_with_empty_roles(admin_client: TestClient) -> None:
    response = _upload(admin_client)

    assert response.status_code == 201
    assert response.json()["roles"] == []


def test_update_fields_with_roles_persists_fieldless_roles(admin_client: TestClient) -> None:
    """A role with no fields yet must survive a save/reload round-trip."""
    template_id = _upload(admin_client).json()["id"]

    response = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": [_field("Employee")], "roles": ["Employee", "Manager"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["Employee", "Manager"]

    fetched = admin_client.get(f"/api/templates/{template_id}")
    assert fetched.json()["roles"] == ["Employee", "Manager"]


def test_update_fields_without_roles_derives_them_from_fields(admin_client: TestClient) -> None:
    """Old clients that only send ``fields`` keep working: roles are derived in field order."""
    template_id = _upload(admin_client).json()["id"]
    fields = [_field("Manager", "f1"), _field("Employee", "f2"), _field("Manager", "f3")]

    response = admin_client.put(f"/api/templates/{template_id}/fields", json={"fields": fields})

    assert response.status_code == 200, response.text
    assert response.json()["roles"] == ["Manager", "Employee"]


def test_update_fields_rejects_field_role_missing_from_roles(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": [_field("Ghost")], "roles": ["Employee"]},
    )

    assert response.status_code == 422
    assert "Ghost" in response.text


def test_update_fields_rejects_duplicate_roles(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": [], "roles": ["Employee", "Employee"]},
    )

    assert response.status_code == 422


def test_update_fields_rejects_blank_role_names(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = admin_client.put(
        f"/api/templates/{template_id}/fields",
        json={"fields": [], "roles": ["   "]},
    )

    assert response.status_code == 422


# --- list / get / archive ------------------------------------------------


def test_list_templates_allowed_for_non_admin_sender(user_client: TestClient) -> None:
    response = user_client.get("/api/templates")

    assert response.status_code == 200


def test_get_template_not_found_returns_404(admin_client: TestClient) -> None:
    response = admin_client.get("/api/templates/999999")

    assert response.status_code == 404


def test_archive_template_hides_from_list(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]
    assert len(admin_client.get("/api/templates").json()) == 1

    archive_response = admin_client.post(f"/api/templates/{template_id}/archive")
    assert archive_response.status_code == 200

    listing = admin_client.get("/api/templates")
    assert listing.json() == []

    # Still directly fetchable by id.
    fetched = admin_client.get(f"/api/templates/{template_id}")
    assert fetched.status_code == 200


def test_archive_template_404_for_missing_template(admin_client: TestClient) -> None:
    response = admin_client.post("/api/templates/999999/archive")

    assert response.status_code == 404


# --- file serving: template-pdf ------------------------------------------


def test_template_pdf_served_to_admin(admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = admin_client.get(f"/api/files/template-pdf/{template_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_template_pdf_403_for_unrelated_user(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = user_client.get(f"/api/files/template-pdf/{template_id}")

    assert response.status_code == 403


def test_template_pdf_404_for_missing_template(admin_client: TestClient) -> None:
    response = admin_client.get("/api/files/template-pdf/999999")

    assert response.status_code == 404


def test_template_pdf_allowed_for_submitter(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    template_id = _upload(admin_client).json()["id"]
    admin_id = admin_client.get("/api/auth/me").json()["id"]
    user_id = user_client.get("/api/auth/me").json()["id"]

    submission = Submission(template_id=template_id, title="Send it", created_by=admin_id)
    db.add(submission)
    db.flush()
    db.add(Submitter(submission_id=submission.id, user_id=user_id, role="Signer 1"))
    db.commit()

    response = user_client.get(f"/api/files/template-pdf/{template_id}")

    assert response.status_code == 200


def test_template_pdf_allowed_for_sender_of_submission(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    """A sender who used someone else's template — without being a signer on
    it — can still open the document from their envelope page."""
    template_id = _upload(admin_client).json()["id"]
    admin_id = admin_client.get("/api/auth/me").json()["id"]
    user_id = user_client.get("/api/auth/me").json()["id"]

    submission = Submission(template_id=template_id, title="Sent by non-creator", created_by=user_id)
    db.add(submission)
    db.flush()
    # The sender is not among the submitters — only the admin signs.
    db.add(Submitter(submission_id=submission.id, user_id=admin_id, role="Signer 1"))
    db.commit()

    response = user_client.get(f"/api/files/template-pdf/{template_id}")

    assert response.status_code == 200


def test_template_pdf_requires_login(client: TestClient, admin_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = client.get(f"/api/files/template-pdf/{template_id}")

    assert response.status_code == 401


# --- file serving: signed-pdf ---------------------------------------------


def test_signed_pdf_allowed_for_sender(admin_client: TestClient, db: Session, app_settings: Settings) -> None:
    template_id = _upload(admin_client).json()["id"]
    admin_id = admin_client.get("/api/auth/me").json()["id"]

    storage = get_storage(app_settings)
    storage.save("submissions/1/signed.pdf", b"%PDF-1.4 signed")

    submission = Submission(
        template_id=template_id,
        title="Send it",
        created_by=admin_id,
        signed_pdf_key="submissions/1/signed.pdf",
    )
    db.add(submission)
    db.commit()

    response = admin_client.get(f"/api/files/signed-pdf/{submission.id}")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 signed"


def test_signed_pdf_allowed_for_submitter(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    template_id = _upload(admin_client).json()["id"]
    admin_id = admin_client.get("/api/auth/me").json()["id"]
    user_id = user_client.get("/api/auth/me").json()["id"]

    storage = get_storage(app_settings)
    storage.save("submissions/1/signed.pdf", b"%PDF-1.4 signed")

    submission = Submission(
        template_id=template_id,
        title="Send it",
        created_by=admin_id,
        signed_pdf_key="submissions/1/signed.pdf",
    )
    db.add(submission)
    db.flush()
    db.add(Submitter(submission_id=submission.id, user_id=user_id, role="Signer 1"))
    db.commit()

    response = user_client.get(f"/api/files/signed-pdf/{submission.id}")

    assert response.status_code == 200


def test_signed_pdf_403_for_unrelated_user(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    template_id = _upload(admin_client).json()["id"]
    admin_id = admin_client.get("/api/auth/me").json()["id"]

    submission = Submission(
        template_id=template_id,
        title="Send it",
        created_by=admin_id,
        signed_pdf_key="submissions/1/signed.pdf",
    )
    db.add(submission)
    db.commit()

    response = user_client.get(f"/api/files/signed-pdf/{submission.id}")

    assert response.status_code == 403


def test_signed_pdf_404_when_not_yet_signed(admin_client: TestClient, db: Session) -> None:
    template_id = _upload(admin_client).json()["id"]
    admin_id = admin_client.get("/api/auth/me").json()["id"]

    submission = Submission(template_id=template_id, title="Send it", created_by=admin_id)
    db.add(submission)
    db.commit()

    response = admin_client.get(f"/api/files/signed-pdf/{submission.id}")

    assert response.status_code == 404


def test_signed_pdf_404_for_missing_submission(admin_client: TestClient) -> None:
    response = admin_client.get("/api/files/signed-pdf/999999")

    assert response.status_code == 404


# --- file serving: signature -----------------------------------------------


def test_signature_image_served_to_owner(user_client: TestClient, db: Session, app_settings: Settings) -> None:
    user_id = user_client.get("/api/auth/me").json()["id"]
    storage = get_storage(app_settings)
    storage.save("signatures/1/image.png", b"\x89PNG\r\n\x1a\nfake")

    signature = Signature(user_id=user_id, image_key="signatures/1/image.png")
    db.add(signature)
    db.commit()

    response = user_client.get(f"/api/files/signature/{signature.id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_signature_image_served_to_admin(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    user_id = user_client.get("/api/auth/me").json()["id"]
    storage = get_storage(app_settings)
    storage.save("signatures/1/image.png", b"\x89PNG\r\n\x1a\nfake")

    signature = Signature(user_id=user_id, image_key="signatures/1/image.png")
    db.add(signature)
    db.commit()

    response = admin_client.get(f"/api/files/signature/{signature.id}")

    assert response.status_code == 200


def test_signature_image_403_for_other_user(
    user_client: TestClient,
    admin_client: TestClient,
    db: Session,
) -> None:
    admin_id = admin_client.get("/api/auth/me").json()["id"]
    signature = Signature(user_id=admin_id, image_key="signatures/1/image.png")
    db.add(signature)
    db.commit()

    response = user_client.get(f"/api/files/signature/{signature.id}")

    assert response.status_code == 403


def test_signature_image_404_for_missing_signature(admin_client: TestClient) -> None:
    response = admin_client.get("/api/files/signature/999999")

    assert response.status_code == 404


# --- per-user scoping ---------------------------------------------------------


def test_list_templates_shows_only_own(admin_client: TestClient, user_client: TestClient) -> None:
    """Templates are private to their creator — the list never shows another user's."""
    _upload(admin_client, name="Admins Template")
    _upload(user_client, name="Users Template")

    admin_names = [t["name"] for t in admin_client.get("/api/templates").json()]
    user_names = [t["name"] for t in user_client.get("/api/templates").json()]

    assert admin_names == ["Admins Template"]
    assert user_names == ["Users Template"]


def test_get_template_of_another_user_is_403_for_non_admin(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    assert user_client.get(f"/api/templates/{template_id}").status_code == 403


def test_admin_can_get_another_users_template(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload(user_client).json()["id"]

    assert admin_client.get(f"/api/templates/{template_id}").status_code == 200


def test_update_fields_on_another_users_template_is_403(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    response = user_client.put(f"/api/templates/{template_id}/fields", json={"fields": [], "roles": ["Signer 1"]})

    assert response.status_code == 403


def test_archive_another_users_template_is_403(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload(admin_client).json()["id"]

    assert user_client.post(f"/api/templates/{template_id}/archive").status_code == 403


# --- copy ---------------------------------------------------------------


def _add_field(client: TestClient, template_id: int) -> None:
    fields = [
        {
            "id": "f1",
            "type": "signature",
            "role": "Signer 1",
            "page": 0,
            "x": 0.1,
            "y": 0.1,
            "w": 0.2,
            "h": 0.05,
            "required": True,
        },
    ]
    resp = client.put(f"/api/templates/{template_id}/fields", json={"fields": fields})
    assert resp.status_code == 200, resp.text


def test_copy_template_creates_owned_copy_with_fields_and_files(
    admin_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    from app.models import Template

    source_id = _upload(admin_client, name="Offer Letter").json()["id"]
    _add_field(admin_client, source_id)

    resp = admin_client.post(f"/api/templates/{source_id}/copy")

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] != source_id
    assert body["name"] == "Copy of Offer Letter"
    assert body["page_count"] == 2
    assert [f["id"] for f in body["fields"]] == ["f1"]

    source = db.get(Template, source_id)
    copy = db.get(Template, body["id"])
    assert copy.shared is False
    assert copy.is_adhoc is False
    # Independent storage: the copy owns its own files.
    assert copy.pdf_key != source.pdf_key
    assert copy.original_file_key != source.original_file_key
    storage = get_storage(app_settings)
    assert storage.exists(copy.pdf_key)
    assert storage.exists(copy.original_file_key)


def test_copy_tolerates_missing_original_file(
    admin_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    """The original upload is archival — its absence must not block copying."""
    from app.models import Template

    source_id = _upload(admin_client).json()["id"]
    source = db.get(Template, source_id)
    get_storage(app_settings).delete(source.original_file_key)

    resp = admin_client.post(f"/api/templates/{source_id}/copy")

    assert resp.status_code == 201, resp.text
    copy = db.get(Template, resp.json()["id"])
    assert copy.original_file_key == ""
    assert get_storage(app_settings).exists(copy.pdf_key)


def test_copy_with_missing_pdf_file_is_409(
    admin_client: TestClient,
    db: Session,
    app_settings: Settings,
) -> None:
    """A copy without its working PDF would be unusable — fail cleanly, not 500."""
    from app.models import Template

    source_id = _upload(admin_client).json()["id"]
    source = db.get(Template, source_id)
    get_storage(app_settings).delete(source.pdf_key)

    resp = admin_client.post(f"/api/templates/{source_id}/copy")

    assert resp.status_code == 409
    assert resp.json()["detail"]


def test_copy_shared_template_by_non_owner(
    admin_client: TestClient,
    user_client: TestClient,
    db: Session,
) -> None:
    from app.models import Template

    source_id = _upload(admin_client, name="Org NDA").json()["id"]
    assert admin_client.put(f"/api/templates/{source_id}/sharing", json={"shared": True}).status_code == 200

    resp = user_client.post(f"/api/templates/{source_id}/copy")

    assert resp.status_code == 201, resp.text
    copy = db.get(Template, resp.json()["id"])
    user_id = user_client.get("/api/auth/me").json()["id"]
    assert copy.created_by == user_id
    # The copy starts private even though the source was shared.
    assert copy.shared is False


def test_copy_private_template_of_another_user_is_403(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    source_id = _upload(admin_client).json()["id"]

    assert user_client.post(f"/api/templates/{source_id}/copy").status_code == 403


def test_copy_archived_template_is_409(admin_client: TestClient) -> None:
    source_id = _upload(admin_client).json()["id"]
    assert admin_client.post(f"/api/templates/{source_id}/archive").status_code == 200

    assert admin_client.post(f"/api/templates/{source_id}/copy").status_code == 409


def test_copy_template_requires_can_send(user_client: TestClient, db: Session) -> None:
    source_id = _upload(user_client).json()["id"]
    user = db.get(User, user_client.get("/api/auth/me").json()["id"])
    user.can_send = False
    db.commit()

    assert user_client.post(f"/api/templates/{source_id}/copy").status_code == 403


def test_owner_can_fetch_own_template_pdf(user_client: TestClient) -> None:
    """A non-admin sender must be able to load their own template's PDF in the builder."""
    template_id = _upload(user_client).json()["id"]

    response = user_client.get(f"/api/files/template-pdf/{template_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
