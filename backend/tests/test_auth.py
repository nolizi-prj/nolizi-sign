"""Tests for Entra ID auth, sessions, and dev bypass.

No test hits the real Microsoft identity platform: the login route validates
``next`` before ever constructing an MSAL app, and the callback's only
testable logic (claims -> user upsert, tenant validation) is factored into
``app.auth.upsert_user_from_claims`` and exercised directly with fake claims
dicts instead of going through ``/api/auth/callback``.
"""

from collections.abc import Callable

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import require_admin, require_sender, upsert_user, upsert_user_from_claims
from app.config import Settings
from app.models import User

ADMIN_EMAIL = "admin@pumasi.ai"


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "session_secret": "test-session-secret",
        "admin_emails": ADMIN_EMAIL,
        "dev_auth_bypass": True,
        "app_base_url": "http://testserver",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture
def dev_client(make_client: Callable[[Settings | None], TestClient]) -> TestClient:
    """A TestClient backed by an app with DEV_AUTH_BYPASS enabled."""
    return make_client(_settings())


def test_dev_login_sets_cookie_and_me_returns_user(dev_client: TestClient) -> None:
    response = dev_client.post("/api/auth/dev-login", json={"email": "user@pumasi.ai", "name": "Test User"})

    assert response.status_code == 200
    assert "sign_session" in response.cookies

    me = dev_client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "user@pumasi.ai"
    assert body["name"] == "Test User"
    assert body["is_admin"] is False
    assert "id" in body


def test_dev_login_admin_email_gets_is_admin_true(dev_client: TestClient) -> None:
    response = dev_client.post("/api/auth/dev-login", json={"email": ADMIN_EMAIL.upper(), "name": "Admin"})

    assert response.status_code == 200
    assert response.json()["is_admin"] is True


def test_me_without_cookie_returns_401(dev_client: TestClient) -> None:
    response = dev_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_dev_login_404_when_flag_unset(make_client: Callable[[Settings | None], TestClient]) -> None:
    client = make_client(_settings(dev_auth_bypass=False))

    response = client.post("/api/auth/dev-login", json={"email": "user@pumasi.ai", "name": "Test User"})

    assert response.status_code == 404


def test_login_rejects_absolute_next_url(dev_client: TestClient) -> None:
    response = dev_client.get("/api/auth/login", params={"next": "https://evil.com"}, follow_redirects=False)

    assert response.status_code == 400


def test_login_rejects_scheme_relative_next_url(dev_client: TestClient) -> None:
    response = dev_client.get("/api/auth/login", params={"next": "//evil.com"}, follow_redirects=False)

    assert response.status_code == 400


def test_login_rejects_backslash_next_url(dev_client: TestClient) -> None:
    """Browsers normalize a leading /\\ to // (WHATWG backslash trick) — must be rejected too."""
    response = dev_client.get("/api/auth/login", params={"next": "/\\evil.com"}, follow_redirects=False)

    assert response.status_code == 400


def test_login_rejects_leading_backslash_slash_next_url(dev_client: TestClient) -> None:
    response = dev_client.get("/api/auth/login", params={"next": "\\/evil.com"}, follow_redirects=False)

    assert response.status_code == 400


def test_logout_clears_session(dev_client: TestClient) -> None:
    dev_client.post("/api/auth/dev-login", json={"email": "user@pumasi.ai", "name": "Test User"})

    logout_response = dev_client.post("/api/auth/logout")
    assert logout_response.status_code == 200

    me = dev_client.get("/api/auth/me")
    assert me.status_code == 401


def test_current_user_rejects_tampered_cookie(dev_client: TestClient) -> None:
    dev_client.cookies.set("sign_session", "not-a-valid-token")

    response = dev_client.get("/api/auth/me")

    assert response.status_code == 401


def test_upsert_user_from_claims_creates_user(db: Session) -> None:
    settings = _settings(ms_tenant_id="tenant-123")
    claims = {
        "tid": "tenant-123",
        "preferred_username": "New.User@Pumasi.ai",
        "name": "New User",
        "oid": "oid-abc",
    }

    user = upsert_user_from_claims(db, claims, settings)

    assert user.email == "new.user@pumasi.ai"
    assert user.name == "New User"
    assert user.entra_oid == "oid-abc"
    assert user.is_admin is False


def test_upsert_user_from_claims_admin_email(db: Session) -> None:
    settings = _settings(ms_tenant_id="tenant-123")
    claims = {"tid": "tenant-123", "preferred_username": ADMIN_EMAIL, "name": "Admin", "oid": "oid-1"}

    user = upsert_user_from_claims(db, claims, settings)

    assert user.is_admin is True


def test_upsert_user_from_claims_rejects_tenant_mismatch(db: Session) -> None:
    settings = _settings(ms_tenant_id="tenant-123")
    claims = {"tid": "other-tenant", "preferred_username": "user@pumasi.ai", "name": "User", "oid": "oid-2"}

    with pytest.raises(HTTPException) as exc_info:
        upsert_user_from_claims(db, claims, settings)

    assert exc_info.value.status_code == 403


def test_upsert_user_reasserts_admin_on_existing_user(db: Session) -> None:
    settings = _settings(ms_tenant_id="tenant-123")
    existing = User(email=ADMIN_EMAIL, name="Old Name", is_admin=False)
    db.add(existing)
    db.commit()

    user = upsert_user(db, email=ADMIN_EMAIL, name="Admin Name", entra_oid="oid-9", settings=settings)

    assert user.id == existing.id
    assert user.name == "Admin Name"
    assert user.is_admin is True


def test_upsert_user_does_not_revoke_admin_when_email_removed_from_list(db: Session) -> None:
    """A previously-flagged admin keeps is_admin even if ADMIN_EMAILS no longer lists them."""
    settings = _settings(admin_emails="someone-else@pumasi.ai", ms_tenant_id="tenant-123")
    existing = User(email=ADMIN_EMAIL, name="Old Name", is_admin=True)
    db.add(existing)
    db.commit()

    user = upsert_user(db, email=ADMIN_EMAIL, name="Admin Name", entra_oid=None, settings=settings)

    assert user.is_admin is True


def test_allowed_email_domains_defaults_to_pumasi() -> None:
    assert Settings().allowed_email_domains_list == ["pumasi.ai"]


def test_allowed_email_domains_list_parses_and_normalizes() -> None:
    settings = Settings(allowed_email_domains=" Pumasi.ai , example.org ,")

    assert settings.allowed_email_domains_list == ["pumasi.ai", "example.org"]


def test_require_admin_returns_user_when_admin() -> None:
    admin = User(id=1, email=ADMIN_EMAIL, name="Admin", is_admin=True)

    assert require_admin(admin) is admin


def test_require_admin_rejects_non_admin() -> None:
    user = User(id=2, email="user@pumasi.ai", name="User", is_admin=False)

    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin required"


def test_external_user_session_is_rejected(admin_client, make_client, app_settings, db) -> None:
    admin_client.post("/api/users", json={"email": "ext@vendor.com", "name": "Ext"})
    # dev-login issues a session cookie for the (external) row...
    ext_client = make_client(app_settings)
    ext_client.post("/api/auth/dev-login", json={"email": "ext@vendor.com", "name": "Ext"})

    # ...but current_user refuses to resolve it.
    assert ext_client.get("/api/auth/me").status_code == 401


def test_entra_login_upgrades_external_to_internal(db) -> None:
    from app.auth import upsert_user_from_claims
    from app.config import Settings
    from app.models import User

    settings = Settings(ms_tenant_id="tenant-1")
    db.add(User(email="hired@vendor.com", name="Hired", is_external=True))
    db.commit()

    claims = {"tid": "tenant-1", "preferred_username": "hired@vendor.com", "name": "Hired Person", "oid": "oid-1"}
    user = upsert_user_from_claims(db, claims, settings)

    assert user.is_external is False


def test_admin_emails_never_promotes_external(db) -> None:
    from app.auth import upsert_user
    from app.config import Settings
    from app.models import User

    db.add(User(email="ext@vendor.com", name="Ext", is_external=True))
    db.commit()
    settings = Settings(admin_emails="ext@vendor.com")

    user = upsert_user(db, email="ext@vendor.com", name="Ext", entra_oid=None, settings=settings)

    assert user.is_admin is False


# --- can_send / require_sender ---------------------------------------------


def test_me_reports_effective_can_send(make_client, app_settings) -> None:
    client = make_client(app_settings)
    client.post("/api/auth/dev-login", json={"email": "sender@pumasi.ai", "name": "Sender"})
    assert client.get("/api/auth/me").json()["can_send"] is True


def test_require_sender_blocks_revoked_user(make_client, app_settings, db) -> None:
    client = make_client(app_settings)
    client.post("/api/auth/dev-login", json={"email": "norights@pumasi.ai", "name": "No Rights"})
    user = db.query(User).filter_by(email="norights@pumasi.ai").one()
    user.can_send = False
    db.commit()
    assert client.get("/api/auth/me").json()["can_send"] is False


def test_require_sender_returns_admin_regardless_of_can_send() -> None:
    admin = User(id=1, email=ADMIN_EMAIL, name="Admin", is_admin=True, can_send=False, is_external=False)

    assert require_sender(admin) is admin


def test_require_sender_returns_internal_user_with_can_send() -> None:
    user = User(id=2, email="user@pumasi.ai", name="User", is_admin=False, can_send=True, is_external=False)

    assert require_sender(user) is user


def test_require_sender_rejects_internal_user_without_can_send() -> None:
    user = User(id=3, email="user@pumasi.ai", name="User", is_admin=False, can_send=False, is_external=False)

    with pytest.raises(HTTPException) as exc_info:
        require_sender(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Sender access required"


def test_require_sender_rejects_external_user_even_with_can_send() -> None:
    user = User(id=4, email="ext@vendor.com", name="Ext", is_admin=False, can_send=True, is_external=True)

    with pytest.raises(HTTPException) as exc_info:
        require_sender(user)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Sender access required"
