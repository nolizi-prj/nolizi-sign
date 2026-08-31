"""Tests for the users API: list (signer pickers/admin console) and admin update.

``admin_client``/``user_client`` (from conftest) share one ``app_settings``
instance per test, so both are visible to each other via the same test
database.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User

ADMIN_EMAIL = "admin@pumasi.ai"
DEFAULT_USER_EMAIL = "user@pumasi.ai"


def _me_id(client: TestClient) -> int:
    return client.get("/api/auth/me").json()["id"]


# --- list -----------------------------------------------------------------


def test_plain_pumasi_user_can_list_users(make_client, app_settings) -> None:
    client = make_client(app_settings)
    client.post("/api/auth/dev-login", json={"email": "plain@pumasi.ai", "name": "Plain"})
    assert client.get("/api/users").status_code == 200


def test_list_users_returns_all_users(admin_client: TestClient, user_client: TestClient) -> None:
    admin_id = _me_id(admin_client)
    user_id = _me_id(user_client)

    resp = admin_client.get("/api/users")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {u["id"] for u in body}
    assert admin_id in ids
    assert user_id in ids
    by_id = {u["id"]: u for u in body}
    assert by_id[admin_id]["is_admin"] is True
    assert by_id[user_id]["is_admin"] is False
    assert by_id[user_id]["email"] == DEFAULT_USER_EMAIL


# --- create -----------------------------------------------------------------


def test_create_user_allowed_for_non_admin_sender(user_client: TestClient) -> None:
    resp = user_client.post("/api/users", json={"email": "new@pumasi.ai"})
    assert resp.status_code == 201, resp.text


def test_create_user_requires_sender(user_client: TestClient, db: Session) -> None:
    user_id = _me_id(user_client)
    user = db.get(User, user_id)
    user.can_send = False
    db.commit()

    resp = user_client.post("/api/users", json={"email": "new@pumasi.ai"})
    assert resp.status_code == 403


def test_create_user_provisions_by_email(admin_client: TestClient) -> None:
    resp = admin_client.post("/api/users", json={"email": "jane.doe@pumasi.ai"})

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "jane.doe@pumasi.ai"
    assert body["name"] == "Jane Doe"
    assert body["is_admin"] is False
    assert body["is_external"] is False

    # Visible in the listing, so signer pickers can offer them immediately.
    listing = admin_client.get("/api/users").json()
    assert any(u["id"] == body["id"] for u in listing)


def test_create_user_normalizes_email(admin_client: TestClient) -> None:
    resp = admin_client.post("/api/users", json={"email": "  Jane.Doe@Pumasi.ai "})

    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "jane.doe@pumasi.ai"


def test_create_user_existing_email_returns_existing(admin_client: TestClient, user_client: TestClient) -> None:
    existing_id = _me_id(user_client)

    resp = admin_client.post("/api/users", json={"email": DEFAULT_USER_EMAIL.upper()})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == existing_id
    # The existing user's real name is untouched by re-provisioning.
    assert body["name"] == "User"


def test_create_user_rejects_disallowed_domain(admin_client: TestClient) -> None:
    """External-domain addresses (outside ALLOWED_EMAIL_DOMAINS) can be provisioned
    as external signers if a name is provided, but require a name since they can't
    correct a placeholder on their (nonexistent) first login."""
    resp = admin_client.post("/api/users", json={"email": "outsider@gmail.com"})

    assert resp.status_code == 422
    assert "name" in resp.json()["detail"].lower()


def test_create_user_rejects_invalid_email(admin_client: TestClient) -> None:
    for bad in ("not-an-email", "missing@domain", "@pumasi.ai", ""):
        resp = admin_client.post("/api/users", json={"email": bad})
        assert resp.status_code == 422, f"{bad!r}: {resp.status_code}"


# --- update -----------------------------------------------------------------


def test_update_user_requires_admin(user_client: TestClient) -> None:
    resp = user_client.put("/api/users/1", json={"is_admin": True})
    assert resp.status_code == 403


def test_update_user_not_found(admin_client: TestClient) -> None:
    resp = admin_client.put("/api/users/999999", json={"is_admin": True})
    assert resp.status_code == 404


def test_update_user_toggles_admin_flag(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)

    resp = admin_client.put(f"/api/users/{user_id}", json={"is_admin": True})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == user_id
    assert body["is_admin"] is True

    # Reflected on the next request too, not just the response body.
    listing = admin_client.get("/api/users").json()
    assert next(u for u in listing if u["id"] == user_id)["is_admin"] is True


def test_update_user_self_demotion_returns_409(
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    admin_a = make_client(app_settings)
    admin_a.post("/api/auth/dev-login", json={"email": ADMIN_EMAIL, "name": "Admin A"})
    admin_a_id = _me_id(admin_a)

    resp = admin_a.put(f"/api/users/{admin_a_id}", json={"is_admin": False})

    assert resp.status_code == 409

    # Still an admin — the demotion never happened.
    me = admin_a.get("/api/auth/me").json()
    assert me["is_admin"] is True


def test_admin_can_demote_another_admin(
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> None:
    admin_a = make_client(app_settings)
    admin_a.post("/api/auth/dev-login", json={"email": ADMIN_EMAIL, "name": "Admin A"})

    admin_b = make_client(app_settings)
    admin_b.post("/api/auth/dev-login", json={"email": "admin-b@pumasi.ai", "name": "Admin B"})
    admin_b_id = _me_id(admin_b)
    admin_a.put(f"/api/users/{admin_b_id}", json={"is_admin": True})

    resp = admin_a.put(f"/api/users/{admin_b_id}", json={"is_admin": False})

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_admin"] is False


# --- external signers ---------------------------------------------------------


def test_create_external_user_with_name(admin_client: TestClient) -> None:
    response = admin_client.post("/api/users", json={"email": "bob@vendor.com", "name": "Bob Vendor"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@vendor.com"
    assert body["name"] == "Bob Vendor"
    assert body["is_external"] is True


def test_create_external_user_without_name_is_422(admin_client: TestClient) -> None:
    response = admin_client.post("/api/users", json={"email": "bob@vendor.com"})

    assert response.status_code == 422
    assert response.json()["detail"] == "External signer requires a name"


def test_create_internal_user_is_not_external(admin_client: TestClient) -> None:
    response = admin_client.post("/api/users", json={"email": "new.person@pumasi.ai"})

    assert response.status_code == 201
    assert response.json()["is_external"] is False


def test_create_user_rejects_one_char_tld(admin_client: TestClient) -> None:
    # A name is supplied so this can only fail on the email format itself,
    # not the separate "external signer requires a name" 422.
    resp = admin_client.post("/api/users", json={"email": "x@y.c", "name": "X Y"})
    assert resp.status_code == 422
    assert "email" in resp.json()["detail"][0]["loc"]


# --- contact correction ------------------------------------------------------


def test_sender_corrects_external_user_email(user_client: TestClient, admin_client: TestClient) -> None:
    created = admin_client.post("/api/users", json={"email": "bob@gmail.co", "name": "Bob Vendor"})
    assert created.status_code == 201, created.text
    external_id = created.json()["id"]

    resp = user_client.put(f"/api/users/{external_id}", json={"email": "bob@gmail.com"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["email"] == "bob@gmail.com"

    # Persisted, not just the response body.
    listing = admin_client.get("/api/users").json()
    assert next(u for u in listing if u["id"] == external_id)["email"] == "bob@gmail.com"


def test_sender_cannot_edit_internal_user_name(user_client: TestClient, admin_client: TestClient) -> None:
    target_id = _me_id(admin_client)

    resp = user_client.put(f"/api/users/{target_id}", json={"name": "New Name"})

    assert resp.status_code == 403
    assert "external" in resp.json()["detail"].lower()


def test_admin_cannot_edit_internal_user_name(admin_client: TestClient) -> None:
    # Internal identity comes from SSO/login, not a manual edit — this
    # applies to internal targets even when the caller is an admin.
    admin_id = _me_id(admin_client)

    resp = admin_client.put(f"/api/users/{admin_id}", json={"name": "New Admin Name"})

    assert resp.status_code == 403
    assert "external" in resp.json()["detail"].lower()


def test_update_user_null_email_is_422(admin_client: TestClient) -> None:
    external = admin_client.post("/api/users", json={"email": "frank@vendor.com", "name": "Frank"})
    external_id = external.json()["id"]

    resp = admin_client.put(f"/api/users/{external_id}", json={"email": None})

    assert resp.status_code == 422


def test_update_user_empty_name_is_422(admin_client: TestClient) -> None:
    external = admin_client.post("/api/users", json={"email": "grace@vendor.com", "name": "Grace"})
    external_id = external.json()["id"]

    resp = admin_client.put(f"/api/users/{external_id}", json={"name": ""})

    assert resp.status_code == 422


def test_update_user_email_collision_returns_409(admin_client: TestClient) -> None:
    external = admin_client.post("/api/users", json={"email": "carol@vendor.com", "name": "Carol"})
    external_id = external.json()["id"]
    other = admin_client.post("/api/users", json={"email": "dave@vendor.com", "name": "Dave"})
    other_email = other.json()["email"]

    resp = admin_client.put(f"/api/users/{external_id}", json={"email": other_email})

    assert resp.status_code == 409


def test_update_user_internal_domain_email_on_external_user_is_422(admin_client: TestClient) -> None:
    external = admin_client.post("/api/users", json={"email": "erin@vendor.com", "name": "Erin"})
    external_id = external.json()["id"]

    resp = admin_client.put(f"/api/users/{external_id}", json={"email": "erin@pumasi.ai"})

    assert resp.status_code == 422
    assert "external" in resp.json()["detail"].lower()


def test_sender_toggling_admin_flag_is_403(user_client: TestClient) -> None:
    user_id = _me_id(user_client)

    resp = user_client.put(f"/api/users/{user_id}", json={"is_admin": True})

    assert resp.status_code == 403


def test_admin_can_toggle_can_send(admin_client: TestClient, user_client: TestClient) -> None:
    user_id = _me_id(user_client)

    resp = admin_client.put(f"/api/users/{user_id}", json={"can_send": False})

    assert resp.status_code == 200, resp.text
    assert resp.json()["can_send"] is False


def test_external_user_is_created_with_can_send_false(admin_client: TestClient) -> None:
    """Externals can never send (require_sender excludes them regardless), so
    the stored flag must say so too — a can_send=true row renders a
    misleadingly 'on' (disabled) toggle in the admin user list."""
    response = admin_client.post("/api/users", json={"email": "noflag@vendor.com", "name": "No Flag"})

    assert response.status_code == 201, response.text
    assert response.json()["can_send"] is False


def test_enabling_can_send_or_admin_on_external_is_422(admin_client: TestClient) -> None:
    external = admin_client.post("/api/users", json={"email": "hardgate@vendor.com", "name": "Hard Gate"})
    external_id = external.json()["id"]

    can_send = admin_client.put(f"/api/users/{external_id}", json={"can_send": True})
    assert can_send.status_code == 422

    is_admin = admin_client.put(f"/api/users/{external_id}", json={"is_admin": True})
    assert is_admin.status_code == 422

    # Explicitly setting them false stays allowed (a no-op normalization).
    off = admin_client.put(f"/api/users/{external_id}", json={"can_send": False, "is_admin": False})
    assert off.status_code == 200, off.text
    assert off.json()["can_send"] is False
