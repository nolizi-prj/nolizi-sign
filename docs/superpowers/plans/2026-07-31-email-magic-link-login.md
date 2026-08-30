# Email Magic-Link Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Passwordless email magic-link login alongside the existing Entra SSO, restricted to `@pumasi.ai`, per `docs/superpowers/specs/2026-07-31-email-magic-link-login-design.md`.

**Architecture:** Two new endpoints on the existing auth router — `POST /api/auth/email/request` (send a 15-minute `itsdangerous` link via the Graph mailer) and `GET /api/auth/email/callback` (verify, enforce single-use via a new `users.email_login_min_iat` column, set the normal session cookie). Frontend gets a public `/login` page offering both SSO and email; the router guard and 401 interceptor send unauthenticated users there instead of hard-redirecting into SSO.

**Tech Stack:** FastAPI, itsdangerous, SQLAlchemy/Alembic (Postgres), pytest, Vue 3 + Vuetify, vue-router, axios.

## Global Constraints

- Tests are Postgres-only; test DB from `TEST_DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`). Run pytest from `backend/` with the venv at `backend/.venv`.
- Lint: `ruff check . && ruff format --check .` from `backend/` must pass.
- Frontend: `npx vue-tsc --noEmit` and `npm run build` from `frontend/` must pass.
- Never log email addresses, tokens, or message bodies (mailer docstring rule).
- Generic responses on the request endpoint: ineligible domain and rate-limited both return the same 200 body — no information leak.
- Magic-link expiry is 900 seconds; rate limit is 3 sends per email per 900 seconds.
- All new emails/copy use the product name "Pumasi Sign".

---

### Task 1: Config setting, model column, migration

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/models.py` (User class, ~line 28)
- Create: `backend/migrations/versions/b7e1a9c4d2f0_add_email_login_min_iat.py`
- Test: `backend/tests/test_auth.py` (append)

**Interfaces:**
- Produces: `Settings.allowed_email_domains: str` (default `"pumasi.ai"`), `Settings.allowed_email_domains_list: list[str]` property; `User.email_login_min_iat: datetime | None` (TIMESTAMPTZ, nullable).

- [ ] **Step 1: Write failing tests** — append to `backend/tests/test_auth.py`:

```python
def test_allowed_email_domains_defaults_to_pumasi() -> None:
    assert Settings().allowed_email_domains_list == ["pumasi.ai"]


def test_allowed_email_domains_list_parses_and_normalizes() -> None:
    settings = Settings(allowed_email_domains=" Pumasi.com , example.org ,")

    assert settings.allowed_email_domains_list == ["pumasi.ai", "example.org"]
```

- [ ] **Step 2: Run to verify failure**

Run (from `backend/`): `.venv/Scripts/python -m pytest tests/test_auth.py -k allowed_email_domains -v`
Expected: FAIL — `AttributeError: ... allowed_email_domains_list`

- [ ] **Step 3: Implement**

In `backend/app/config.py`, after `admin_emails: str = ""` add the field, and after the `admin_emails_list` property add:

```python
    allowed_email_domains: str = "pumasi.ai"
```

```python
    @property
    def allowed_email_domains_list(self) -> list[str]:
        """Return ALLOWED_EMAIL_DOMAINS as lowercased, trimmed domain names."""
        return [domain.strip().lower() for domain in self.allowed_email_domains.split(",") if domain.strip()]
```

In `backend/app/models.py`, in `User` after `is_admin`:

```python
    email_login_min_iat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Create `backend/migrations/versions/b7e1a9c4d2f0_add_email_login_min_iat.py`:

```python
"""Add users.email_login_min_iat for magic-link single-use enforcement.

Tokens issued at or before this timestamp are rejected; set to the token's
issue time on every successful email login.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e1a9c4d2f0"
down_revision = "cbfd8b9b5c8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_login_min_iat", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email_login_min_iat")
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: all PASS (table is recreated from ORM metadata each session, so the column exists in tests automatically).

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/models.py backend/migrations/versions/b7e1a9c4d2f0_add_email_login_min_iat.py backend/tests/test_auth.py
git commit -m "feat: ALLOWED_EMAIL_DOMAINS setting and email_login_min_iat column"
```

---

### Task 2: Magic-link serializer + `POST /api/auth/email/request`

**Files:**
- Modify: `backend/app/auth.py` (constants + serializer next to `authflow_serializer`)
- Modify: `backend/app/routers/auth.py`
- Test: `backend/tests/test_email_login.py` (create)

**Interfaces:**
- Consumes: `Settings.allowed_email_domains_list` (Task 1), `mailer.send(settings, to, subject, html) -> bool` (existing, never raises), `_is_safe_relative_path` (existing).
- Produces: in `app.auth` — `MAGICLINK_SALT = "sign-magiclink"`, `MAGIC_LINK_MAX_AGE_SECONDS = 900`, `magiclink_serializer(settings) -> URLSafeTimedSerializer`; in `app.routers.auth` — route `POST /api/auth/email/request` (body `{"email": str, "next": str | None}`, always `{"ok": true}` except 502 on mail failure), module state `_email_login_sends: dict[str, list[float]]`, constants `MAGIC_LINK_RATE_LIMIT = 3`, `MAGIC_LINK_RATE_WINDOW_SECONDS = 900`.

- [ ] **Step 1: Write failing tests** — create `backend/tests/test_email_login.py`:

```python
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

from app import mailer
from app.config import Settings
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
    response = email_client.post("/api/auth/email/request", json={"email": "User@Pumasi.com", "next": "/send/3"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert len(sent_mails) == 1
    assert sent_mails[0]["to"] == ["user@pumasi.ai"]
    assert "/api/auth/email/callback?token=" in str(sent_mails[0]["html"])


def test_request_ineligible_domain_returns_generic_200_and_sends_nothing(
    email_client: TestClient, sent_mails: list[dict[str, object]]
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


def test_request_mailer_failure_returns_502(
    email_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mailer, "send", lambda *args, **kwargs: False)

    response = email_client.post("/api/auth/email/request", json={"email": "user@pumasi.ai"})

    assert response.status_code == 502


def test_request_unsafe_next_falls_back_to_root(
    email_client: TestClient, sent_mails: list[dict[str, object]]
) -> None:
    email_client.post("/api/auth/email/request", json={"email": "user@pumasi.ai", "next": "https://evil.com"})

    from app.auth import MAGIC_LINK_MAX_AGE_SECONDS, magiclink_serializer

    html = str(sent_mails[0]["html"])
    token = parse_qs(urlparse(html.split('href="')[1].split('"')[0]).query)["token"][0]
    data = magiclink_serializer(_settings()).loads(token, max_age=MAGIC_LINK_MAX_AGE_SECONDS)
    assert data["next"] == "/"
    assert data["email"] == "user@pumasi.ai"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_email_login.py -v`
Expected: FAIL — `AttributeError: module 'app.routers.auth' has no attribute '_email_login_sends'` (and 404s if it got further).

- [ ] **Step 3: Implement**

In `backend/app/auth.py`, after the `AUTHFLOW_*` constants add:

```python
MAGICLINK_SALT = "sign-magiclink"
MAGIC_LINK_MAX_AGE_SECONDS = 15 * 60
```

and after `authflow_serializer`:

```python
def magiclink_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Return the itsdangerous serializer used for email magic-link tokens."""
    return URLSafeTimedSerializer(settings.session_secret, salt=MAGICLINK_SALT)
```

Also extend the module docstring's cookie list with a third bullet noting the `sign-magiclink` salt is for emailed login tokens (not a cookie), kept on a distinct salt for the same non-confusion reason.

In `backend/app/routers/auth.py`:

Add imports: `import html as html_module`, `import time`, `from urllib.parse import quote, urlparse` (extend the existing urlparse import), `from app import mailer`, and add `MAGIC_LINK_MAX_AGE_SECONDS, magiclink_serializer` to the `from app.auth import (...)` block.

Add module-level state and the route (place after `dev_login`):

```python
MAGIC_LINK_RATE_LIMIT = 3
MAGIC_LINK_RATE_WINDOW_SECONDS = 15 * 60

# In-process rate-limit state: normalized email -> recent send times
# (time.time()). Fine for a single-process uvicorn deployment; revisit if the
# app ever runs multiple workers.
_email_login_sends: dict[str, list[float]] = {}


class EmailLoginRequest(BaseModel):
    """Body for POST /api/auth/email/request."""

    email: str
    next: str | None = None


@router.post("/email/request")
def email_login_request(
    payload: EmailLoginRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    """Email a magic sign-in link to an allowed-domain address.

    Always returns a generic ``{"ok": true}`` for ineligible domains and
    rate-limited addresses so the endpoint doesn't reveal who can log in;
    502 only when a send was actually attempted and the mailer failed.
    """
    email = payload.email.strip().lower()
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain not in settings.allowed_email_domains_list:
        return {"ok": True}

    now = time.time()
    recent = [ts for ts in _email_login_sends.get(email, []) if now - ts < MAGIC_LINK_RATE_WINDOW_SECONDS]
    if len(recent) >= MAGIC_LINK_RATE_LIMIT:
        _email_login_sends[email] = recent
        return {"ok": True}

    next_path = payload.next if payload.next and _is_safe_relative_path(payload.next) else "/"
    token = magiclink_serializer(settings).dumps({"email": email, "next": next_path})
    link = f"{settings.app_base_url}/api/auth/email/callback?token={quote(token)}"
    body = (
        "<p>Use the button below to sign in to Pumasi Sign. "
        "The link expires in 15 minutes and can be used once.</p>"
        f'<p><a href="{html_module.escape(link)}" style="{MAGIC_LINK_BUTTON_STYLE}">Sign in</a></p>'
        "<p>If you didn't request this, you can ignore this email.</p>"
    )
    if not mailer.send(settings, [email], "Your Pumasi Sign sign-in link", body):
        raise HTTPException(status_code=502, detail="Could not send the sign-in email")

    recent.append(now)
    _email_login_sends[email] = recent
    return {"ok": True}
```

with, near the other module constants:

```python
MAGIC_LINK_BUTTON_STYLE = (
    "display:inline-block;padding:10px 20px;background:#2563eb;color:#ffffff;"
    "text-decoration:none;border-radius:6px;font-family:sans-serif;"
)
```

(Same visual style as `notifications._BUTTON_STYLE`; kept separate because that constant is private to the notifications module.)

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_email_login.py tests/test_auth.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth.py backend/app/routers/auth.py backend/tests/test_email_login.py
git commit -m "feat: POST /api/auth/email/request sends magic sign-in link"
```

---

### Task 3: `GET /api/auth/email/callback`

**Files:**
- Modify: `backend/app/routers/auth.py`
- Test: `backend/tests/test_email_login.py` (append)

**Interfaces:**
- Consumes: `magiclink_serializer`, `MAGIC_LINK_MAX_AGE_SECONDS`, `upsert_user`, `set_session_cookie`, `_is_safe_relative_path`, `User.email_login_min_iat` (Task 1).
- Produces: route `GET /api/auth/email/callback?token=...` → 302 to `next` with `sign_session` cookie on success; 302 to `/login?error=expired` on any invalid/expired/replayed token.

- [ ] **Step 1: Write failing tests** — append to `backend/tests/test_email_login.py` (add `from sqlalchemy.orm import Session` and `from app.models import User` to the file's imports):

```python
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
    assert me.json()["name"] == "new.person"


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
```

Note for the implementer: `MAGIC_LINK_MAX_AGE_SECONDS` must therefore be read as `auth_router.MAGIC_LINK_MAX_AGE_SECONDS`-style module attribute inside the callback (i.e. reference the name imported into `app.routers.auth` at call time, which `monkeypatch.setattr(auth_router, ...)` replaces — this works because the route body references the module-global name, not a captured local).

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest tests/test_email_login.py -v`
Expected: new tests FAIL with 404 (route doesn't exist); Task 2 tests still PASS.

- [ ] **Step 3: Implement** — add to `backend/app/routers/auth.py` (after `email_login_request`):

```python
_EXPIRED_REDIRECT = "/login?error=expired"


@router.get("/email/callback")
def email_login_callback(
    token: str = Query(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Verify a magic-link token, enforce single use, and start a session.

    Any failure (bad signature, expired, replayed, domain no longer allowed)
    redirects to the login page with a generic "expired" notice — the token
    came from an email link, so a JSON error would be user-hostile and a
    specific one would leak which check failed.
    """
    try:
        data, issued_at = magiclink_serializer(settings).loads(
            token, max_age=MAGIC_LINK_MAX_AGE_SECONDS, return_timestamp=True
        )
        email = data["email"]
    except (BadSignature, SignatureExpired, KeyError, TypeError):
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    if domain not in settings.allowed_email_domains_list:
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None and existing.email_login_min_iat is not None and issued_at <= existing.email_login_min_iat:
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)

    name = existing.name if existing is not None else email.split("@", 1)[0]
    user = upsert_user(db, email=email, name=name, entra_oid=None, settings=settings)
    user.email_login_min_iat = issued_at
    db.commit()

    next_path = data.get("next") or "/"
    if not _is_safe_relative_path(next_path):
        next_path = "/"

    response = RedirectResponse(url=next_path, status_code=302)
    set_session_cookie(response, user.id, settings)
    return response
```

`itsdangerous.loads(..., return_timestamp=True)` returns an aware UTC `datetime`; comparison with the TIMESTAMPTZ column is aware-vs-aware. `SignatureExpired` subclasses `BadSignature` but both are listed for clarity, matching `current_user`'s style. The plain `from app.auth import MAGIC_LINK_MAX_AGE_SECONDS` import is correct for the expiry test: it creates a global binding in `app.routers.auth`, the route body resolves the bare name in that module's globals at call time, and `monkeypatch.setattr(auth_router, "MAGIC_LINK_MAX_AGE_SECONDS", -1)` replaces exactly that binding.

- [ ] **Step 4: Run tests + lint**

Run: `.venv/Scripts/python -m pytest tests/test_email_login.py tests/test_auth.py -v` then `.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format .`
Expected: all PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py backend/tests/test_email_login.py
git commit -m "feat: GET /api/auth/email/callback verifies magic link and starts session"
```

---

### Task 4: Frontend login page + routing changes

**Files:**
- Create: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/utils/http.ts`

**Interfaces:**
- Consumes: `POST /api/auth/email/request` (Task 2), existing `GET /api/auth/login?next=`.
- Produces: route `/login` (name `login`, `meta.public`), `loginPageUrl(next: string): string` in `utils/http.ts`.

- [ ] **Step 1: Add `loginPageUrl` and repoint the 401 interceptor** — in `frontend/src/utils/http.ts`, after `loginRedirectUrl` add:

```typescript
/** SPA login page (SSO button + email link form), preserving the target path. */
export function loginPageUrl(next: string): string {
  return "/login?next=" + encodeURIComponent(next);
}
```

and in the interceptor replace `window.location.href = loginRedirectUrl(next);` with `window.location.href = loginPageUrl(next);`. Update the file's header comment: 401s now land on the SPA's `/login` page (which offers Entra SSO and email magic-link) instead of hard-redirecting straight into Entra.

- [ ] **Step 2: Register the route and update the guard** — in `frontend/src/router/index.ts`:

Add to `routes` (next to `signed-out`):

```typescript
  {
    path: "/login",
    name: "login",
    component: () => import("../views/LoginView.vue"),
    // Reachable without a session, or nobody could ever log in.
    meta: { public: true },
  },
```

In `beforeEach`, replace the `window.location.href = loginRedirectUrl(to.fullPath); return false;` branch with:

```typescript
  if (!auth.me) {
    return { name: "login", query: { next: to.fullPath } };
  }
```

Remove the now-unused `loginRedirectUrl` import and update the header comment (guard now routes to `/login` instead of hard-redirecting to Entra).

- [ ] **Step 3: Create `frontend/src/views/LoginView.vue`:**

```vue
<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import http, { loginRedirectUrl } from "../utils/http";

const route = useRoute();

const next = computed(() => {
  const raw = route.query.next;
  // Same-origin relative paths only; anything else falls back to the dashboard.
  return typeof raw === "string" && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
});
const ssoUrl = computed(() => loginRedirectUrl(next.value));
const linkExpired = computed(() => route.query.error === "expired");

const email = ref("");
const sending = ref(false);
const sent = ref(false);
const sendFailed = ref(false);

async function requestLink() {
  if (!email.value.trim()) return;
  sending.value = true;
  sendFailed.value = false;
  try {
    await http.post(
      "/auth/email/request",
      { email: email.value.trim(), next: next.value },
      { skipAuthRedirect: true },
    );
    sent.value = true;
  } catch {
    sendFailed.value = true;
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <v-container class="d-flex justify-center pt-16">
    <v-card max-width="480" width="100%" class="pa-4">
      <v-card-title class="text-center">Sign in to Pumasi Sign</v-card-title>
      <v-card-text>
        <v-alert v-if="linkExpired" type="warning" variant="tonal" density="compact" class="mb-4">
          That sign-in link has expired or was already used. Request a new one below.
        </v-alert>

        <div class="text-center">
          <v-btn color="primary" variant="flat" :href="ssoUrl" prepend-icon="mdi-microsoft" block>
            Sign in with Microsoft
          </v-btn>
        </div>

        <div class="d-flex align-center my-5">
          <v-divider />
          <span class="text-caption text-medium-emphasis mx-3">or</span>
          <v-divider />
        </div>

        <template v-if="!sent">
          <form @submit.prevent="requestLink">
            <v-text-field
              v-model="email"
              label="Work email"
              type="email"
              autocomplete="email"
              density="comfortable"
              :disabled="sending"
            />
            <v-btn type="submit" variant="tonal" block :loading="sending" :disabled="!email.trim()">
              Email me a sign-in link
            </v-btn>
          </form>
          <p v-if="sendFailed" class="text-caption text-error mt-2 mb-0 text-center">
            Couldn't send the email. Please try again.
          </p>
        </template>
        <v-alert v-else type="success" variant="tonal" density="compact">
          If that address is eligible, a sign-in link is on its way. Check your inbox — the link
          expires in 15 minutes.
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>
```

- [ ] **Step 4: Type-check and build**

Run (from `frontend/`): `npx vue-tsc --noEmit` then `npm run build`
Expected: both succeed with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/router/index.ts frontend/src/utils/http.ts
git commit -m "feat: /login page with Microsoft SSO and email magic-link options"
```

---

### Task 5: Docs + full verification

**Files:**
- Modify: `README.md` (env var table)
- Modify: `CLAUDE.md` (Key facts bullet about login)

**Interfaces:** none — documentation and final gate.

- [ ] **Step 1: Document the env var** — in `README.md`'s environment variable table, add a row alongside `ADMIN_EMAILS`:

```markdown
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated email domains allowed to use magic-link email login (default `pumasi.ai`) |
```

(Match the table's actual column layout when editing.)

- [ ] **Step 2: Update CLAUDE.md** — extend the "Local login" key-facts bullet:

```markdown
- Local login uses `DEV_AUTH_BYPASS=1` (`/api/auth/dev-login`); production
  uses Entra ID SSO or passwordless email magic links (`/login`, domains
  gated by `ALLOWED_EMAIL_DOMAINS`, default `pumasi.ai`).
  `DEV_AUTH_BYPASS` must never be set in production.
```

- [ ] **Step 3: Full verification**

Run from `backend/`: `.venv/Scripts/python -m pytest` and `.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .`
Run from `frontend/`: `npx vue-tsc --noEmit && npm run build`
Expected: everything passes (docx/xlsx conversion tests may auto-skip without LibreOffice).

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: ALLOWED_EMAIL_DOMAINS env var and email login notes"
```
