"""Shared templates: any sender can see, read, and send from a shared
template; only the owner (or an admin) can edit, archive, or toggle sharing."""

from fastapi.testclient import TestClient

from .test_signing import _field, _me_id, _upload_template


def _share(client: TestClient, template_id: int, shared: bool = True) -> None:
    resp = client.put(f"/api/templates/{template_id}/sharing", json={"shared": shared})
    assert resp.status_code == 200, resp.text


def test_shared_template_appears_in_other_senders_list(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    assert template_id not in [t["id"] for t in user_client.get("/api/templates").json()]

    _share(admin_client, template_id)

    listed = user_client.get("/api/templates").json()
    row = next(t for t in listed if t["id"] == template_id)
    assert row["shared"] is True
    assert row["owner"]["email"] == "admin@pumasi.ai"


def test_own_unshared_template_reports_owner_and_flag(admin_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    row = next(t for t in admin_client.get("/api/templates").json() if t["id"] == template_id)
    assert row["shared"] is False
    assert row["owner"]["email"] == "admin@pumasi.ai"


def test_non_owner_can_read_and_send_from_shared_template(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])

    assert user_client.get(f"/api/templates/{template_id}").status_code == 403
    _share(admin_client, template_id)
    assert user_client.get(f"/api/templates/{template_id}").status_code == 200

    resp = user_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Sent from a shared template",
            "signers": [{"role": "Signer 1", "user_id": _me_id(admin_client)}],
        },
    )
    assert resp.status_code == 201, resp.text


def test_non_owner_cannot_send_from_unshared_template(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    resp = user_client.post(
        "/api/submissions",
        json={
            "template_id": template_id,
            "title": "Not allowed",
            "signers": [{"role": "Signer 1", "user_id": _me_id(admin_client)}],
        },
    )
    assert resp.status_code == 403


def test_non_owner_cannot_edit_archive_or_toggle_shared_template(
    admin_client: TestClient,
    user_client: TestClient,
) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    _share(admin_client, template_id)

    assert user_client.put(f"/api/templates/{template_id}/fields", json={"fields": []}).status_code == 403
    assert user_client.post(f"/api/templates/{template_id}/archive").status_code == 403
    assert user_client.put(f"/api/templates/{template_id}/sharing", json={"shared": False}).status_code == 403


def test_unsharing_hides_the_template_again(admin_client: TestClient, user_client: TestClient) -> None:
    template_id = _upload_template(admin_client, [_field("sig", "signature", "Signer 1")])
    _share(admin_client, template_id)
    assert template_id in [t["id"] for t in user_client.get("/api/templates").json()]

    _share(admin_client, template_id, shared=False)
    assert template_id not in [t["id"] for t in user_client.get("/api/templates").json()]
    assert user_client.get(f"/api/templates/{template_id}").status_code == 403
