"""Tests for passwordless email magic-link login.

The Graph mailer is monkeypatched at ``app.mailer.send`` (the routers module
calls it as ``mailer.send(...)``, so patching the attribute on the mailer
module is sufficient); no test touches the network. Tokens for callback tests
are minted directly with ``magiclink_serializer`` using the same
session_secret the test app is configured with.
"""

from collections.abc import Callable, Generator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import mailer
from app.config import Settings
from app.models import User
from app.routers import auth as auth_router

TEST_SECRET = "test-session-secret"


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "session_secret": TEST_SECRET,
        "app_base_url": "http://testserver",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Generator[None, None, None]:
    """Module-level rate-limit state survives across TestClients; clear it per test."""
    auth_router._email_login_sends.clear()
    yield
    auth_router._email_login_sends.clear()


@pytest.fixture
def sent_mails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Capture mailer.send calls; append dicts with to/subject/html."""
    calls: list[dict[str, object]] = []

    def _fake_send(settings: Settings, to: list[str], subject: str, html: str, *args: object, **kwargs: object) -> bool:
        calls.append({"to": to, "subject": subject, "html": html})
        return True

    monkeypatch.setattr(mailer, "send", _fake_send)
    return calls


@pytest.fixture
def email_client(make_client: Callable[[Settings | None], TestClient]) -> TestClient:
    return make_client(_settings())


def test_request_sends_link_to_allowed_domain(email_client: TestClient, sent_mails: list[dict[str, object]]) -> None:
    response = email_client.post("/api/auth/email/request", json={"email": "User@Pumasi.ai", "next": "/send/3"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(sent_mails) == 1
    assert sent_mails[0]["to"] == ["user@pumasi.ai"]
    assert "/api/auth/email/callback?token=" in str(sent_mails[0]["html"])


def test_request_ineligible_domain_returns_generic_200_and_sends_nothing(
    email_client: TestClient,
    sent_mails: list[dict[str, object]],
) -> None:
    response = email_client.post("/api/auth/email/request", json={"email": "someone@gmail.com"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent_mails == []


def test_request_rate_limited_after_three_sends(email_client: TestClient, sent_mails: list[dict[str, object]]) -> None:
    for _ in range(4):
        response = email_client.post("/api/auth/email/request", json={"email": "user@pumasi.ai"})
        assert response.status_code == 200

    assert len(sent_mails) == 3


def test_request_mailer_failure_returns_502(email_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mailer, "send", lambda *args, **kwargs: False)

    response = email_client.post("/api/auth/email/request", json={"email": "user@pumasi.ai"})

    assert response.status_code == 502


def test_request_unsafe_next_falls_back_to_root(
    email_client: TestClient,
    sent_mails: list[dict[str, object]],
) -> None:
    email_client.post("/api/auth/email/request", json={"email": "user@pumasi.ai", "next": "https://evil.com"})

    from app.auth import MAGIC_LINK_MAX_AGE_SECONDS, magiclink_serializer

    html = str(sent_mails[0]["html"])
    token = parse_qs(urlparse(html.split('href="')[1].split('"')[0]).query)["token"][0]
    data = magiclink_serializer(_settings()).loads(token, max_age=MAGIC_LINK_MAX_AGE_SECONDS)
    assert data["next"] == "/"
    assert data["email"] == "user@pumasi.ai"


def _mint_token(email: str, next_path: str = "/") -> str:
    from app.auth import magiclink_serializer

    return magiclink_serializer(_settings()).dumps({"email": email, "next": next_path})


def test_callback_logs_in_new_user_and_redirects_to_next(email_client: TestClient) -> None:
    token = _mint_token("new.person@pumasi.ai", "/send/7")

    response = email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/send/7"
    assert "sign_session" in response.cookies

    me = email_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "new.person@pumasi.ai"
    # Placeholder name via placeholder_name_from_email — same derivation as
    # POST /api/users provisioning, overwritten by their first SSO login.
    assert me.json()["name"] == "New Person"


def test_callback_keeps_existing_users_name(email_client: TestClient, db: Session) -> None:
    # Create the user with a real name first (as SSO would have).
    db.add(User(email="user@pumasi.ai", name="Real Name"))
    db.commit()

    token = _mint_token("user@pumasi.ai")
    email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    me = email_client.get("/api/auth/me")
    assert me.json()["name"] == "Real Name"


def test_callback_rejects_tampered_token(email_client: TestClient) -> None:
    token = _mint_token("user@pumasi.ai") + "x"

    response = email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=expired"
    assert "sign_session" not in response.cookies


def test_callback_rejects_expired_token(email_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = _mint_token("user@pumasi.ai")
    monkeypatch.setattr(auth_router, "MAGIC_LINK_MAX_AGE_SECONDS", -1)

    response = email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login?error=expired"


def test_callback_rejects_replayed_token(email_client: TestClient) -> None:
    token = _mint_token("user@pumasi.ai")

    first = email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)
    assert first.status_code == 302
    assert first.headers["location"] == "/"

    email_client.post("/api/auth/logout")
    second = email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    assert second.headers["location"] == "/login?error=expired"
    me = email_client.get("/api/auth/me")
    assert me.status_code == 401


def test_callback_rechecks_domain_against_current_config(
    make_client: Callable[[Settings | None], TestClient],
) -> None:
    token = _mint_token("user@pumasi.ai")
    client = make_client(_settings(allowed_email_domains="example.org"))

    response = client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    assert response.headers["location"] == "/login?error=expired"


def test_callback_unsafe_next_in_token_falls_back_to_root(email_client: TestClient) -> None:
    token = _mint_token("user@pumasi.ai", "//evil.com")

    response = email_client.get("/api/auth/email/callback", params={"token": token}, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_magic_link_request_silently_skips_external_user(make_client, db, monkeypatch) -> None:
    from app import mailer
    from app.config import Settings
    from app.models import User

    sent: list = []
    monkeypatch.setattr(mailer, "send", lambda *a, **k: sent.append(a) or True)
    # vendor.com is allowed here to prove the is_external flag alone blocks login.
    settings = Settings(
        session_secret="s",
        allowed_email_domains="pumasi.ai,vendor.com",
        app_base_url="http://testserver",
    )
    client = make_client(settings)
    db.add(User(email="ext@vendor.com", name="Ext", is_external=True))
    db.commit()

    response = client.post("/api/auth/email/request", json={"email": "ext@vendor.com"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent == []
