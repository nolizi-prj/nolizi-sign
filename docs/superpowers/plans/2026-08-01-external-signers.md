# External Signers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let external (non-pumasi.ai) recipients sign envelopes via an emailed token link plus a one-time email verification code, and add decline-to-sign for all recipients.

**Architecture:** External signers become `users` rows flagged `is_external=true` (never able to log in), so every downstream identity consumer (audit, certificate, stamping, signature storage) works unchanged. Their sign link carries a random `access_uid`; a 6-digit emailed code exchanges it for a scoped `sign_signer` cookie that the existing `/api/sign/*` endpoints accept alongside the session cookie. Decline voids the whole envelope. Spec: `docs/superpowers/specs/2026-08-01-external-signers-design.md`.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + itsdangerous (backend), Vue 3 + Vuetify + vue-router (frontend), pytest + Playwright.

## Global Constraints

- Tests are **Postgres-only** — never SQLite. Test DB URL from `TEST_DATABASE_URL`, default `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`.
- Backend commands run from `backend/` **using the main checkout's venv** (worktrees reuse it — see memory note): `/home/m/dev/pumasi-sign\backend\.venv\Scripts\python.exe`. Below, `PY` means that interpreter. Frontend: run `npm ci` fresh in the worktree's `frontend/` before the first frontend task.
- If pytest fails with cascading `UndefinedTable` errors, another session is using the shared test DB — just re-run.
- Lint before every commit: `PY -m ruff check . && PY -m ruff format .` (backend), `npx vue-tsc --noEmit` (frontend).
- Never commit secrets. `DEV_AUTH_BYPASS` gates all dev-only endpoints (404 when off) — mirror the `dev-login` pattern.
- All work happens on branch `worktree-external-signers` in this worktree. Commit after every task.
- New cookie: `sign_signer`, salt `sign-signer`, payload `{"sid": <submitter_id>}`, max-age 4 h, httponly, samesite=lax, secure iff HTTPS — identical flag rules to `sign_session`.
- Verification codes: 6 digits, sha256-hashed at rest, 10-min expiry, 5 attempts per code, 3 sends/15 min per submitter (+10/15 min per IP).

---

### Task 1: Migration + model changes

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/migrations/versions/a7e42b9c1d05_external_signers.py`
- Test: `backend/tests/test_external_signing.py` (new file)

**Interfaces:**
- Produces: `User.is_external: bool`; `Submitter.access_uid: str | None`, `Submitter.verification_code_hash: str | None`, `Submitter.verification_code_expires_at: datetime | None`, `Submitter.verification_attempts: int`, `Submitter.declined_at: datetime | None`, `Submitter.decline_reason: str | None`; `"declined"` valid in `SUBMISSION_STATUSES`, `SUBMITTER_STATUSES`, `AUDIT_EVENTS`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_external_signing.py
"""Tests for external-signer support: model columns, provisioning, token flow, decline."""

from app.models import AuditEvent, Submission, Submitter, Template, User


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v`
Expected: FAIL with `TypeError: 'is_external' is an invalid keyword argument for User`

- [ ] **Step 3: Update `backend/app/models.py`**

Change the three constants (lines 24-26):

```python
SUBMISSION_STATUSES = ("pending", "completed", "cancelled", "declined")
SUBMITTER_STATUSES = ("pending", "opened", "completed", "declined")
AUDIT_EVENTS = ("created", "sent", "opened", "signed", "reminded", "completed", "cancelled", "declined")
```

In `User`, after `is_admin`:

```python
    # External signer: has no login of any kind — their only access path is a
    # signed token link scoped to one submitter (see routers/signing.py).
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
```

In `Submitter`, after `email_status`:

```python
    # External signing (docs/superpowers/specs/2026-08-01-external-signers-design.md):
    # access_uid is the random secret in an external signer's emailed link
    # (NULL for internal signers); the verification_* columns hold the current
    # emailed 6-digit code (sha256 hex), its expiry, and failed-attempt count.
    access_uid: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    verification_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 4: Write the migration**

First confirm the current head: `cd backend && PY -m alembic heads` — expected `f3a8c1d97e42`. If it differs, use whatever `heads` prints as `down_revision`.

```python
# backend/migrations/versions/a7e42b9c1d05_external_signers.py
"""External signers: users.is_external, submitter token/verification/decline
columns, and 'declined' added to the status/event CHECK constraints."""

import sqlalchemy as sa
from alembic import op

revision = "a7e42b9c1d05"
down_revision = "f3a8c1d97e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_external", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("submitters", sa.Column("access_uid", sa.String(32), nullable=True))
    op.create_unique_constraint("uq_submitters_access_uid", "submitters", ["access_uid"])
    op.add_column("submitters", sa.Column("verification_code_hash", sa.String(64), nullable=True))
    op.add_column("submitters", sa.Column("verification_code_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submitters", sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("submitters", sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submitters", sa.Column("decline_reason", sa.String(500), nullable=True))

    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submissions_status", "submissions", "status IN ('pending', 'completed', 'cancelled', 'declined')"
    )
    op.drop_constraint("ck_submitters_status", "submitters", type_="check")
    op.create_check_constraint(
        "ck_submitters_status", "submitters", "status IN ('pending', 'opened', 'completed', 'declined')"
    )
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_event",
        "audit_events",
        "event IN ('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled', 'declined')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_event",
        "audit_events",
        "event IN ('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled')",
    )
    op.drop_constraint("ck_submitters_status", "submitters", type_="check")
    op.create_check_constraint("ck_submitters_status", "submitters", "status IN ('pending', 'opened', 'completed')")
    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_status", "submissions", "status IN ('pending', 'completed', 'cancelled')")
    op.drop_column("submitters", "decline_reason")
    op.drop_column("submitters", "declined_at")
    op.drop_column("submitters", "verification_attempts")
    op.drop_column("submitters", "verification_code_expires_at")
    op.drop_column("submitters", "verification_code_hash")
    op.drop_constraint("uq_submitters_access_uid", "submitters", type_="unique")
    op.drop_column("submitters", "access_uid")
    op.drop_column("users", "is_external")
```

- [ ] **Step 5: Run tests**

Run: `cd backend && PY -m pytest tests/test_external_signing.py tests/test_db.py -v`
Expected: PASS (conftest recreates tables from the updated models; the migration itself is exercised in prod/CI by `alembic upgrade head`).

- [ ] **Step 6: Lint + commit**

```bash
git add backend/app/models.py backend/migrations/versions/a7e42b9c1d05_external_signers.py backend/tests/test_external_signing.py
git commit -m "feat: schema for external signers and decline-to-sign"
```

---

### Task 2: Provision external users via POST /api/users

**Files:**
- Modify: `backend/app/schemas.py` (UserCreate, UserOut, UserBrief)
- Modify: `backend/app/routers/users.py` (create_user)
- Modify: `backend/app/routers/auth.py` (`_user_out` adds `is_external`)
- Test: `backend/tests/test_users.py`

**Interfaces:**
- Consumes: `User.is_external` (Task 1).
- Produces: `UserCreate` gains `name: str | None`; `UserOut` and `UserBrief` gain `is_external: bool`; external provisioning 422 detail is the exact string `"External signer requires a name"` (the frontend matches on it in Task 12).

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_users.py`, mirroring its existing style)

```python
def test_create_external_user_with_name(admin_client) -> None:
    response = admin_client.post("/api/users", json={"email": "bob@vendor.com", "name": "Bob Vendor"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@vendor.com"
    assert body["name"] == "Bob Vendor"
    assert body["is_external"] is True


def test_create_external_user_without_name_is_422(admin_client) -> None:
    response = admin_client.post("/api/users", json={"email": "bob@vendor.com"})

    assert response.status_code == 422
    assert response.json()["detail"] == "External signer requires a name"


def test_create_internal_user_is_not_external(admin_client) -> None:
    response = admin_client.post("/api/users", json={"email": "new.person@pumasi.ai"})

    assert response.status_code == 201
    assert response.json()["is_external"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_users.py -v`
Expected: the three new tests FAIL (422 domain rejection / missing `is_external` key).

- [ ] **Step 3: Implement**

`schemas.py` — add to `UserCreate` (keep the existing email validator):

```python
    name: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
```

Add `is_external: bool` to `UserOut`, and `is_external: bool` to `UserBrief` (both are `from_attributes` models — no other change needed).

`routers/users.py` — replace the domain-rejection block in `create_user` (and update its docstring to say external domains create `is_external` signer-only users):

```python
    existing = db.scalars(select(User).where(User.email == payload.email)).one_or_none()
    if existing is not None:
        response.status_code = 200
        return existing

    is_external = not email_domain_allowed(payload.email, settings)
    if is_external and not payload.name:
        # The certificate and name-field stamping need a real display name,
        # and an external signer never logs in to correct a placeholder.
        raise HTTPException(status_code=422, detail="External signer requires a name")

    user = User(
        email=payload.email,
        name=payload.name or placeholder_name_from_email(payload.email),
        is_admin=False,
        is_external=is_external,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

`routers/auth.py` — `_user_out` returns `{"id": ..., "email": ..., "name": ..., "is_admin": ..., "is_external": user.is_external}` so the SPA's `User` type stays uniform.

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_users.py tests/test_auth.py -v`
Expected: PASS (including all pre-existing tests).

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/schemas.py backend/app/routers/users.py backend/app/routers/auth.py backend/tests/test_users.py
git commit -m "feat: provision external signers via POST /api/users"
```

---

### Task 3: Login guards — is_external means "can never log in"

**Files:**
- Modify: `backend/app/auth.py` (`current_user`, `upsert_user`, `upsert_user_from_claims`)
- Modify: `backend/app/routers/auth.py` (`email_login_request`, `email_login_callback`)
- Test: `backend/tests/test_auth.py`, `backend/tests/test_email_login.py`

**Interfaces:**
- Consumes: `User.is_external`.
- Produces: `current_user` raises 401 for external users; Entra claims upsert flips `is_external` to False.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_auth.py` (it already has tests exercising `upsert_user_from_claims` and dev-login — follow their fixture style):

```python
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
```

Append to `backend/tests/test_email_login.py` (reuse its existing mailer-capture pattern — it monkeypatches `mailer.send`):

```python
def test_magic_link_request_silently_skips_external_user(make_client, db, monkeypatch) -> None:
    from app import mailer
    from app.config import Settings
    from app.models import User

    sent: list = []
    monkeypatch.setattr(mailer, "send", lambda *a, **k: sent.append(a) or True)
    # vendor.com is allowed here to prove the is_external flag alone blocks login.
    settings = Settings(session_secret="s", allowed_email_domains="pumasi.ai,vendor.com", app_base_url="http://testserver")
    client = make_client(settings)
    db.add(User(email="ext@vendor.com", name="Ext", is_external=True))
    db.commit()

    response = client.post("/api/auth/email/request", json={"email": "ext@vendor.com"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert sent == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_auth.py tests/test_email_login.py -v`
Expected: new tests FAIL (me returns 200 / no upgrade / promotion happens / email sent).

- [ ] **Step 3: Implement**

`app/auth.py`:

1. `current_user` — change the final check to:

```python
    user = db.get(User, uid)
    if user is None or user.is_external:
        # External signers never hold app sessions — their only access path
        # is the sign_signer cookie (see routers/signing.py).
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

2. `upsert_user` — in the `else` (existing-user) branch, guard the promotion:

```python
        if is_admin_email and not user.is_external:
            user.is_admin = True
```

3. `upsert_user_from_claims` — after the `upsert_user(...)` call:

```python
    user = upsert_user(db, email=email, name=name, entra_oid=entra_oid, settings=settings)
    if user.is_external:
        # Tenant-gated Entra login is proof of employment: a contractor who
        # got hired keeps their row (and signing history) and becomes internal.
        user.is_external = False
        db.commit()
        db.refresh(user)
    return user
```

`app/routers/auth.py`:

4. `email_login_request` — add `db: Session = Depends(get_db)` to its parameters, and after the domain check:

```python
    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None and existing.is_external:
        return {"ok": True}  # same silent shape as an ineligible domain
```

5. `email_login_callback` — right after `existing = db.query(User)...` (before the min-iat check):

```python
    if existing is not None and existing.is_external:
        return RedirectResponse(url=_EXPIRED_REDIRECT, status_code=302)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_auth.py tests/test_email_login.py -v`
Expected: PASS, all pre-existing tests included.

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/auth.py backend/app/routers/auth.py backend/tests/test_auth.py backend/tests/test_email_login.py
git commit -m "feat: external users can never obtain a login session"
```

---

### Task 4: Signer-cookie infrastructure in app/auth.py

**Files:**
- Modify: `backend/app/auth.py`
- Test: `backend/tests/test_external_signing.py`

**Interfaces:**
- Produces (used by Tasks 5-7, 9):
  - `SIGNER_COOKIE_NAME = "sign_signer"`, `SIGNER_SALT = "sign-signer"`, `SIGNER_MAX_AGE_SECONDS = 4 * 60 * 60`
  - `signer_serializer(settings: Settings) -> URLSafeTimedSerializer`
  - `set_signer_cookie(response: Response, submitter_id: int, settings: Settings) -> None`
  - `signer_submitter_id(request: Request, settings: Settings) -> int | None` (None on missing/invalid/expired)
  - `optional_user(request, db=Depends(get_db), settings=Depends(get_settings)) -> User | None`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_external_signing.py`)

```python
def test_signer_cookie_round_trip() -> None:
    from unittest.mock import Mock

    from app.auth import SIGNER_COOKIE_NAME, set_signer_cookie, signer_serializer, signer_submitter_id
    from app.config import Settings
    from fastapi import Response

    settings = Settings(session_secret="test-secret", app_base_url="http://testserver")
    response = Response()
    set_signer_cookie(response, 42, settings)
    cookie_header = response.headers["set-cookie"]
    assert SIGNER_COOKIE_NAME in cookie_header and "HttpOnly" in cookie_header

    token = signer_serializer(settings).dumps({"sid": 42})
    request = Mock(cookies={SIGNER_COOKIE_NAME: token})
    assert signer_submitter_id(request, settings) == 42

    # Session-salt tokens must not be accepted as signer cookies.
    from app.auth import session_serializer

    wrong = session_serializer(settings).dumps({"sid": 42})
    request = Mock(cookies={SIGNER_COOKIE_NAME: wrong})
    assert signer_submitter_id(request, settings) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v`
Expected: FAIL with `ImportError: cannot import name 'set_signer_cookie'`

- [ ] **Step 3: Implement** (in `app/auth.py`, after the magic-link constants; extend the module docstring's cookie list with a fourth bullet for `sign_signer`)

```python
SIGNER_COOKIE_NAME = "sign_signer"
SIGNER_SALT = "sign-signer"
SIGNER_MAX_AGE_SECONDS = 4 * 60 * 60


def signer_serializer(settings: Settings) -> URLSafeTimedSerializer:
    """Serializer for the external-signer cookie (distinct salt, same secret)."""
    return URLSafeTimedSerializer(settings.session_secret, salt=SIGNER_SALT)


def set_signer_cookie(response: Response, submitter_id: int, settings: Settings) -> None:
    """Set the scoped ``sign_signer`` cookie granting access to one submitter only."""
    token = signer_serializer(settings).dumps({"sid": submitter_id})
    response.set_cookie(
        key=SIGNER_COOKIE_NAME,
        value=token,
        max_age=SIGNER_MAX_AGE_SECONDS,
        httponly=True,
        secure=_cookie_is_secure(settings),
        samesite="lax",
        path="/",
    )


def signer_submitter_id(request: Request, settings: Settings) -> int | None:
    """Submitter id from a valid ``sign_signer`` cookie, else None (never raises)."""
    token = request.cookies.get(SIGNER_COOKIE_NAME)
    if not token:
        return None
    try:
        data = signer_serializer(settings).loads(token, max_age=SIGNER_MAX_AGE_SECONDS)
        sid = data["sid"]
    except (BadSignature, SignatureExpired, KeyError, TypeError):
        return None
    return sid if isinstance(sid, int) else None


def optional_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    """``current_user``, but None instead of 401 — for routes that also accept the signer cookie."""
    try:
        return current_user(request, db, settings)
    except HTTPException:
        return None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v` — Expected: PASS

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/auth.py backend/tests/test_external_signing.py
git commit -m "feat: scoped sign_signer cookie infrastructure"
```

---

### Task 5: Public token endpoints — landing, request-code, verify

**Files:**
- Modify: `backend/app/routers/signing.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_external_signing.py`

**Interfaces:**
- Consumes: Task 4 cookie helpers; `Submitter.access_uid` + verification columns.
- Produces:
  - `GET /api/sign/token/{access_uid}` → `SignTokenViewOut {status, title, sender_name, masked_email}` with `status ∈ open|already_signed|completed|cancelled|declined`; 404 unknown uid.
  - `POST /api/sign/token/{access_uid}/request-code` → `{"ok": true}` (+ `"dev_code"` when `settings.dev_auth_bypass`); 409 not open, 429 rate-limited, 502 mail failure.
  - `POST /api/sign/token/{access_uid}/verify` body `{"code": str}` → `{"submitter_id": int}` + sets `sign_signer` cookie; 401 wrong code, 410 expired/absent code, 429 attempts exhausted, 409 not open.
  - Test helpers other tasks reuse: `_provision_external`, `_external_submission`, `_capture_mail`, `_last_code`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_external_signing.py`)

```python
import re
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.config import Settings

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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v`
Expected: FAIL — `_external_submission` asserts `access_uid` is set (Task 8 sets it at creation). **For this task only**, temporarily order matters: the access_uid generation lands in Task 8. To keep tasks independently green, add the generation NOW as part of this task (it's two lines) instead of Task 8: see Step 3 item 4. After Step 3, tests must pass.

- [ ] **Step 3: Implement**

1. `schemas.py` — add:

```python
class SignTokenViewOut(BaseModel):
    """Response for GET /api/sign/token/{access_uid} — the external landing page."""

    status: Literal["open", "already_signed", "completed", "cancelled", "declined"]
    title: str
    sender_name: str
    masked_email: str


class SignTokenVerifyIn(BaseModel):
    """Body for POST /api/sign/token/{access_uid}/verify."""

    code: str


class SignTokenVerifyOut(BaseModel):
    """Response for a successful verify: the submitter to drive /api/sign/{id} with."""

    submitter_id: int
```

2. `routers/signing.py` — add imports: `hashlib`, `hmac`, `secrets`, `time`, `from datetime import timedelta`, `from app import mailer`, `from app.auth import set_signer_cookie`, plus `SignTokenVerifyIn, SignTokenVerifyOut, SignTokenViewOut` from schemas, and `Response` from fastapi.

3. Add constants + helpers + the three routes in a new "External token flow" section placed **above** `_get_submitter_authorized`:

```python
VERIFICATION_CODE_TTL_SECONDS = 10 * 60
VERIFICATION_MAX_ATTEMPTS = 5
CODE_SEND_LIMIT = 3
CODE_SEND_IP_LIMIT = 10
CODE_SEND_WINDOW_SECONDS = 15 * 60

# In-process rate-limit state (single-process deployment — same trade-off as
# the magic-link limiter in routers/auth.py).
_code_sends_by_uid: dict[str, list[float]] = {}
_code_sends_by_ip: dict[str, list[float]] = {}


def _over_limit(history: dict[str, list[float]], key: str, limit: int, now: float) -> bool:
    recent = [ts for ts in history.get(key, []) if now - ts < CODE_SEND_WINDOW_SECONDS]
    if len(recent) >= limit:
        history[key] = recent
        return True
    recent.append(now)
    history[key] = recent
    return False


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _get_submitter_by_access_uid(db: Session, access_uid: str) -> Submitter:
    submitter = db.scalars(
        select(Submitter)
        .options(
            selectinload(Submitter.user),
            selectinload(Submitter.submission).selectinload(Submission.template),
        )
        .where(Submitter.access_uid == access_uid),
    ).one_or_none()
    if submitter is None:
        raise HTTPException(status_code=404, detail="Unknown signing link")
    return submitter


def _token_status(submitter: Submitter) -> str:
    submission = submitter.submission
    if submission.status in ("cancelled", "declined", "completed"):
        return submission.status
    if submitter.status == "completed":
        return "already_signed"
    return "open"


@router.get("/token/{access_uid}", response_model=SignTokenViewOut)
def get_token_view(access_uid: str, db: Session = Depends(get_db)) -> SignTokenViewOut:
    """Public landing data for an external sign link: just enough to render
    "we'll email a code to e***@vendor.com" — nothing signable is exposed
    until the code round-trip proves mailbox control."""
    submitter = _get_submitter_by_access_uid(db, access_uid)
    submission = submitter.submission
    sender = db.get(User, submission.created_by)
    return SignTokenViewOut(
        status=_token_status(submitter),
        title=submission.title,
        sender_name=sender.name if sender else "Someone",
        masked_email=_mask_email(submitter.user.email),
    )


@router.post("/token/{access_uid}/request-code")
def request_verification_code(
    access_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Email a fresh 6-digit code to the submitter's own address."""
    submitter = _get_submitter_by_access_uid(db, access_uid)
    if _token_status(submitter) != "open":
        raise HTTPException(status_code=409, detail="This envelope is no longer open for signing")

    now = time.monotonic()
    ip = client_ip(request) or "unknown"
    if _over_limit(_code_sends_by_uid, access_uid, CODE_SEND_LIMIT, now) or _over_limit(
        _code_sends_by_ip, ip, CODE_SEND_IP_LIMIT, now
    ):
        raise HTTPException(status_code=429, detail="Too many code requests; please try again later")

    code = f"{secrets.randbelow(1_000_000):06d}"
    submitter.verification_code_hash = hashlib.sha256(code.encode()).hexdigest()
    submitter.verification_code_expires_at = datetime.now(UTC) + timedelta(seconds=VERIFICATION_CODE_TTL_SECONDS)
    submitter.verification_attempts = 0
    db.commit()

    body = (
        f"<p>Your Pumasi Sign verification code is:</p>"
        f'<p style="font-size:24px;font-weight:bold;letter-spacing:4px;font-family:monospace">{code}</p>'
        "<p>It expires in 10 minutes. If you didn't request this, you can ignore this email.</p>"
    )
    if not mailer.send(settings, [submitter.user.email], "Your Pumasi Sign verification code", body):
        raise HTTPException(status_code=502, detail="Could not send the verification email")

    result: dict = {"ok": True}
    if settings.dev_auth_bypass:
        # e2e-only escape hatch; DEV_AUTH_BYPASS is never set in production.
        result["dev_code"] = code
    return result


@router.post("/token/{access_uid}/verify", response_model=SignTokenVerifyOut)
def verify_code(
    access_uid: str,
    payload: SignTokenVerifyIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SignTokenVerifyOut:
    """Exchange a correct code for the scoped sign_signer cookie."""
    submitter = _get_submitter_by_access_uid(db, access_uid)
    if _token_status(submitter) != "open":
        raise HTTPException(status_code=409, detail="This envelope is no longer open for signing")
    if (
        submitter.verification_code_hash is None
        or submitter.verification_code_expires_at is None
        or datetime.now(UTC) >= submitter.verification_code_expires_at
    ):
        raise HTTPException(status_code=410, detail="Code expired — request a new one")
    if submitter.verification_attempts >= VERIFICATION_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts — request a new code")

    submitted_hash = hashlib.sha256(payload.code.strip().encode()).hexdigest()
    if not hmac.compare_digest(submitted_hash, submitter.verification_code_hash):
        submitter.verification_attempts += 1
        if submitter.verification_attempts >= VERIFICATION_MAX_ATTEMPTS:
            submitter.verification_code_hash = None
            submitter.verification_code_expires_at = None
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect code")

    submitter.verification_code_hash = None
    submitter.verification_code_expires_at = None
    submitter.verification_attempts = 0
    db.commit()
    set_signer_cookie(response, submitter.id, settings)
    return SignTokenVerifyOut(submitter_id=submitter.id)
```

4. Generate `access_uid` at creation (pulled forward from Task 8 so this task's tests can run): in `routers/submissions.py` `_create_submission`, after `_validate_users_exist(db, signers)` add

```python
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_([s.user_id for s in signers])))}
```

and inside the signer loop build the submitter as:

```python
        signer_user = users_by_id[signer.user_id]
        submitter = Submitter(
            submission_id=submission.id,
            user_id=signer.user_id,
            role=signer.role,
            status="pending",
            # External signers get a random link secret; internal signers keep
            # the plain /sign/{id} + login flow.
            access_uid=secrets.token_hex(16) if signer_user.is_external else None,
        )
```

with `import secrets` added to the module.

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_external_signing.py tests/test_signing.py tests/test_submissions.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/routers/signing.py backend/app/routers/submissions.py backend/app/schemas.py backend/tests/test_external_signing.py
git commit -m "feat: public token endpoints for external signer verification"
```

---

### Task 6: Signing endpoints accept the signer cookie

**Files:**
- Modify: `backend/app/routers/signing.py`
- Modify: `backend/app/schemas.py` (`SignerViewOut.my_name`)
- Test: `backend/tests/test_external_signing.py`

**Interfaces:**
- Consumes: `optional_user`, `signer_submitter_id` (Task 4).
- Produces:
  - `SigningIdentity` dataclass `{user: User | None, cookie_submitter_id: int | None}` and dependency `signing_identity(...)` (401 when both empty) — reused by the decline route (Task 9).
  - `_get_submitter_authorized(db, submitter_id, identity)` — new signature.
  - `SignerViewOut` gains `my_name: str`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_external_signing.py`)

```python
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


def test_signer_cookie_cannot_touch_other_submitters_or_app_apis(
    admin_client, user_client, make_client, app_settings, db, monkeypatch
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


def test_external_signer_completes_via_cookie(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)

    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL})
    assert sig.status_code == 200, sig.text
    done = anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig.json()["signature_id"]}})
    assert done.status_code == 200, done.text

    detail = admin_client.get(f"/api/submissions/{submission['id']}").json()
    assert detail["status"] == "completed"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v`
Expected: cookie-based `GET /api/sign/{id}` FAILS with 401 (routes still demand `current_user`), and `my_name` is missing.

- [ ] **Step 3: Implement** (`routers/signing.py`)

1. Imports: `from dataclasses import dataclass`; change the `app.auth` import line to `from app.auth import get_settings, optional_user, set_signer_cookie, signer_submitter_id` (drop `current_user`).

2. Add below the module constants:

```python
@dataclass
class SigningIdentity:
    """Who is calling a /api/sign route: a logged-in internal user, an
    email-verified external signer (signer cookie), or both. At least one
    of the two fields is set — the dependency 401s otherwise."""

    user: User | None
    cookie_submitter_id: int | None


def signing_identity(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SigningIdentity:
    user = optional_user(request, db, settings)
    sid = signer_submitter_id(request, settings)
    if user is None and sid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return SigningIdentity(user=user, cookie_submitter_id=sid)
```

3. Change `_get_submitter_authorized(db, submitter_id, user)` to `(db, submitter_id, identity: SigningIdentity)`; replace the 403 check with:

```python
    session_ok = identity.user is not None and submitter.user_id == identity.user.id
    cookie_ok = identity.cookie_submitter_id == submitter.id
    if not (session_ok or cookie_ok):
        raise HTTPException(status_code=403, detail="Forbidden")
```

4. In all three existing routes (`get_sign_view`, `upload_signature`, `complete_signing`): replace the `user: User = Depends(current_user)` parameter with `identity: SigningIdentity = Depends(signing_identity)`, call `_get_submitter_authorized(db, submitter_id, identity)`, then use `signer = submitter.user` uniformly (for the session path `signer` is the same row as `identity.user`):
   - `get_sign_view`: audit actor `actor_user_id=submitter.user_id`; saved-signature query `Signature.user_id == submitter.user_id`; return `my_name=submitter.user.name`.
   - `upload_signature`: storage key `f"signatures/{submitter.user_id}/{uuid.uuid4().hex}.png"`; `Signature(user_id=submitter.user_id, image_key=key)`.
   - `complete_signing`: `_validate_values(db, submitter.user, my_fields, payload.values)`; audit actor `actor_user_id=submitter.user_id`. Also replace the two cancelled/completed 409 checks with the status-agnostic form (prepares for declined):

```python
    if submission.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is {submission.status}")
```

   - Update the module docstring's authorization sentence to mention the signer cookie.

5. `schemas.py` — add to `SignerViewOut` (after `my_status`):

```python
    # The signer's display name — the signing page renders it into `name`
    # fields; external signers have no auth session to read it from.
    my_name: str
```

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_external_signing.py tests/test_signing.py -v`
Expected: PASS — including every pre-existing test in test_signing.py (session path unchanged). Two possible pre-existing assertions to adjust if they fail: exact response-shape assertions need the new `my_name` key, and the completed-submission 409 detail changed from "Submission is already completed" to "Submission is completed" (the cancelled detail string is unchanged).

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/routers/signing.py backend/app/schemas.py backend/tests/test_external_signing.py
git commit -m "feat: signing endpoints accept the scoped signer cookie"
```

---

### Task 7: File routes accept the signer cookie

**Files:**
- Modify: `backend/app/routers/files.py`
- Test: `backend/tests/test_external_signing.py`

**Interfaces:**
- Consumes: `optional_user`, `signer_submitter_id`.
- Produces: `GET /api/files/template-pdf/{id}` and `GET /api/files/signed-pdf/{id}` work with only the signer cookie (scoped to that submitter's own template/submission); certificate route unchanged (session only).

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_external_signing.py`)

```python
def test_signer_cookie_grants_template_pdf_for_own_envelope_only(
    admin_client, make_client, app_settings, db, monkeypatch
) -> None:
    from tests.test_signing import _field, _upload_template

    anon, submission, _sid, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    own_template = submission["template"]["id"]
    other_template = _upload_template(admin_client, [_field("x", "signature", "Signer 1")], name="Unrelated")

    assert anon.get(f"/api/files/template-pdf/{own_template}").status_code == 200
    assert anon.get(f"/api/files/template-pdf/{other_template}").status_code == 403


def test_signer_cookie_grants_signed_pdf_after_completion(
    admin_client, make_client, app_settings, db, monkeypatch
) -> None:
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, _sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL}).json()["signature_id"]
    anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig}})

    assert anon.get(f"/api/files/signed-pdf/{submission['id']}").status_code == 200
    assert anon.get(f"/api/files/certificate/{submission['id']}").status_code == 401
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v`
Expected: FAIL with 401s on template-pdf/signed-pdf.

- [ ] **Step 3: Implement** (`routers/files.py`)

Imports: `from fastapi import Request`; change auth import to `from app.auth import current_user, get_settings, optional_user, signer_submitter_id`.

Add helper:

```python
def _cookie_submitter(db: Session, request: Request, settings: Settings) -> Submitter | None:
    """The Submitter a valid sign_signer cookie points at, else None."""
    sid = signer_submitter_id(request, settings)
    return db.get(Submitter, sid) if sid is not None else None
```

`get_template_pdf`: change dependency to `user: User | None = Depends(optional_user)` and add `request: Request`. Replace the authorization block:

```python
    if user is not None:
        if not user.is_admin:
            submitter_on_template = db.scalar(
                select(Submitter.id)
                .join(Submission, Submitter.submission_id == Submission.id)
                .where(Submission.template_id == template_id, Submitter.user_id == user.id),
            )
            if submitter_on_template is None:
                raise HTTPException(status_code=403, detail="Forbidden")
    else:
        submitter = _cookie_submitter(db, request, settings)
        if submitter is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if submitter.submission.template_id != template_id:
            raise HTTPException(status_code=403, detail="Forbidden")
```

`_serve_submission_pdf`: change `user: User` parameter to `user: User | None`, add `cookie_submitter: Submitter | None` parameter; replace the check:

```python
    if user is not None:
        is_sender = submission.created_by == user.id
        if not is_sender and not _is_submitter(db, submission_id=submission_id, user_id=user.id):
            raise HTTPException(status_code=403, detail="Forbidden")
    elif cookie_submitter is not None:
        if cookie_submitter.submission_id != submission_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        raise HTTPException(status_code=401, detail="Not authenticated")
```

`get_signed_pdf`: switch to `optional_user` + `request: Request`, pass `cookie_submitter=_cookie_submitter(db, request, settings)`. `get_certificate_pdf`: keep `Depends(current_user)`, pass `cookie_submitter=None`. Update the module docstring's per-resource rules accordingly.

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_external_signing.py tests/test_templates.py tests/test_submissions.py -v` — Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/routers/files.py backend/tests/test_external_signing.py
git commit -m "feat: file routes accept the scoped signer cookie"
```

---

### Task 8: Token links in emails + external-aware completion email

**Files:**
- Modify: `backend/app/notifications.py`
- Test: `backend/tests/test_notifications.py`

**Interfaces:**
- Consumes: `Submitter.access_uid` (set at creation since Task 5), `User.is_external`.
- Produces: `_sign_link(settings, submitter)` (takes the Submitter, not an id) → `/sign/t/{access_uid}` for externals, `/sign/{id}` otherwise; completion email splits into internal (with envelope link) and external (attachment only) sends.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_notifications.py`, reusing its existing fixture/monkeypatch style — it already builds submissions and captures `mailer.send`)

```python
def test_request_email_uses_token_link_for_external(admin_client, db, monkeypatch) -> None:
    from tests.test_external_signing import _capture_mail, _external_submission

    sent = _capture_mail(monkeypatch)
    _submission, access_uid, _sid = _external_submission(admin_client, db)

    request_mail = next(m for m in sent if "requests your signature" in m["subject"])
    assert f"/sign/t/{access_uid}" in request_mail["body"]


def test_completion_email_to_externals_has_no_portal_link(admin_client, make_client, app_settings, db, monkeypatch) -> None:
    from tests.test_external_signing import _last_code, _verified_anon
    from tests.test_signing import PNG_DATA_URL

    anon, submission, submitter_id, sent = _verified_anon(admin_client, make_client, app_settings, db, monkeypatch)
    sig = anon.post(f"/api/sign/{submitter_id}/signature", json={"image": PNG_DATA_URL}).json()["signature_id"]
    anon.post(f"/api/sign/{submitter_id}/complete", json={"values": {"sig1": sig}})

    completion_mails = [m for m in sent if m["subject"].startswith("Completed:")]
    external = next(m for m in completion_mails if "ext@vendor.com" in m["to"])
    internal = next(m for m in completion_mails if "admin@pumasi.ai" in m["to"])
    assert "/envelopes/" not in external["body"]
    assert "/envelopes/" in internal["body"]
    assert external["attachments"] and internal["attachments"]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_notifications.py -v`
Expected: FAIL — request email contains `/sign/{int}`; completion is one combined email with the portal link.

- [ ] **Step 3: Implement** (`notifications.py`)

1. `_sign_link` becomes:

```python
def _sign_link(settings: Settings, submitter: Submitter) -> str:
    """Personal signing URL: token link for external signers, plain id link
    (behind login) for internal ones."""
    if submitter.access_uid:
        return f"{settings.app_base_url}/sign/t/{submitter.access_uid}"
    return f"{settings.app_base_url}/sign/{submitter.id}"
```

Update the two call sites: `on_submission_created` → `_sign_link(settings, submitter)`; `_send_reminder` → `_sign_link(settings, submitter)`.

2. `on_submission_completed` — replace the recipient collection + single send with a partitioned send (sender counts as internal):

```python
    internal: dict[str, None] = {}
    external: dict[str, None] = {}
    for submitter in submission.submitters:
        user = _resolve_user(db, submitter)
        if user is not None:
            (external if user.is_external else internal).setdefault(user.email, None)

    sender = db.get(User, submission.created_by)
    if sender is not None:
        internal.setdefault(sender.email, None)
    for email in internal:
        external.pop(email, None)

    if not internal and not external:
        return
```

(keep the existing attachment block unchanged), then:

```python
    subject = f"Completed: {submission.title}"
    base_body = (
        f"<p>The document <strong>{html.escape(submission.title)}</strong> "
        "has been signed by all parties. The signed PDF is attached.</p>"
    )
    envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
    internal_body = base_body + f'<p><a href="{envelope_link}">View the envelope\'s history and signature certificate</a></p>'

    ok = True
    if internal:
        ok = mailer.send(settings, list(internal), subject, internal_body, attachments) and ok
    if external:
        # No portal link — /envelopes/{id} requires a login externals don't have.
        ok = mailer.send(settings, list(external), subject, base_body, attachments) and ok
    if not ok:
        logger.warning("Failed to send completion email for submission_id=%s", submission.id)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_notifications.py tests/test_jobs.py tests/test_external_signing.py -v` — Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/notifications.py backend/tests/test_notifications.py
git commit -m "feat: token sign links and external-aware completion emails"
```

---

### Task 9: Decline to sign

**Files:**
- Modify: `backend/app/routers/signing.py` (decline route), `backend/app/schemas.py` (`SignDeclineIn`), `backend/app/notifications.py` (`on_submission_declined`)
- Test: `backend/tests/test_external_signing.py`

**Interfaces:**
- Consumes: `signing_identity`, `_get_submitter_authorized`, `"declined"` statuses/event (Task 1).
- Produces: `POST /api/sign/{submitter_id}/decline` body `{"reason": str | null}` → `{"ok": true}`; submitter+submission → `declined`; audit event `declined` (reason in detail); sender emailed.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_external_signing.py`)

```python
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


def test_internal_signer_can_decline_too(admin_client, user_client) -> None:
    from tests.test_signing import _create_submission, _field, _me_id, _submitter_id_for, _upload_template

    template_id = _upload_template(admin_client, [_field("sig1", "signature", "Signer 1")])
    submission = _create_submission(admin_client, template_id, [{"role": "Signer 1", "user_id": _me_id(user_client)}])
    submitter_id = _submitter_id_for(submission, _me_id(user_client))

    assert user_client.post(f"/api/sign/{submitter_id}/decline", json={"reason": None}).status_code == 200
    assert admin_client.get(f"/api/submissions/{submission['id']}").json()["status"] == "declined"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v` — Expected: 404 on the decline route.

- [ ] **Step 3: Implement**

1. `schemas.py`:

```python
class SignDeclineIn(BaseModel):
    """Body for POST /api/sign/{submitter_id}/decline."""

    reason: str | None = Field(None, max_length=500)
```

2. `notifications.py`:

```python
def on_submission_declined(db: Session, submission: Submission, submitter: Submitter, settings: Settings) -> None:
    """Email the sender that a signer declined (with their reason, if given)."""
    sender = db.get(User, submission.created_by)
    if sender is None:
        return
    signer = _resolve_user(db, submitter)
    signer_name = signer.name if signer else "A signer"
    parts = [
        f"<p><strong>{html.escape(signer_name)}</strong> has declined to sign "
        f"<strong>{html.escape(submission.title)}</strong>. The envelope is now void.</p>"
    ]
    if submitter.decline_reason:
        parts.append(f"<p>Reason: {html.escape(submitter.decline_reason)}</p>")
    envelope_link = html.escape(f"{settings.app_base_url}/envelopes/{submission.id}")
    parts.append(f'<p><a href="{envelope_link}">View the envelope</a></p>')
    if not mailer.send(settings, [sender.email], f"Declined: {submission.title}", "\n".join(parts)):
        logger.warning("Failed to send decline email for submission_id=%s", submission.id)
```

3. `routers/signing.py` — add the route after `complete_signing` (import `SignDeclineIn`):

```python
@router.post("/{submitter_id}/decline")
def decline_signing(
    submitter_id: int,
    payload: SignDeclineIn,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    identity: SigningIdentity = Depends(signing_identity),
) -> dict:
    """Decline to sign, voiding the whole envelope.

    The status decision runs under a SELECT ... FOR UPDATE on the submission
    row with populate_existing — same pattern and race rationale as
    routers/submissions.py's cancel_submission (decline races the last
    co-signer's /complete the same way cancel does).
    """
    submitter = _get_submitter_authorized(db, submitter_id, identity)

    submission = db.execute(
        select(Submission)
        .where(Submission.id == submitter.submission_id)
        .with_for_update()
        .execution_options(populate_existing=True),
    ).scalar_one()

    if submission.status != "pending" or submitter.status not in ("pending", "opened"):
        db.rollback()
        raise HTTPException(status_code=409, detail="Submission is not open for signing")

    reason = payload.reason.strip() if payload.reason and payload.reason.strip() else None
    ip = client_ip(request)
    submitter.status = "declined"
    submitter.declined_at = datetime.now(UTC)
    submitter.decline_reason = reason
    submission.status = "declined"
    detail: dict = {"submitter_id": submitter.id}
    if reason:
        detail["reason"] = reason
    audit.record(db, submission.id, "declined", actor_user_id=submitter.user_id, ip=ip, **detail)
    db.commit()

    notifications.on_submission_declined(db, submission, submitter, settings)
    return {"ok": True}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && PY -m pytest tests/test_external_signing.py tests/test_signing.py tests/test_submissions.py tests/test_notifications.py -v` — Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/routers/signing.py backend/app/schemas.py backend/app/notifications.py backend/tests/test_external_signing.py
git commit -m "feat: decline-to-sign voids the envelope and notifies the sender"
```

---

### Task 10: Frontend — types, labels, and SignView as the shared signing component

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/utils/labels.ts`, `frontend/src/views/SignView.vue`, `frontend/src/views/EnvelopeDetailView.vue`

**Interfaces:**
- Consumes: `SignerViewOut.my_name`, decline endpoint, `declined` statuses.
- Produces: `SignView` accepts optional `external?: boolean` prop (skips auth redirects, hides internal-only navigation, renders `my_name`), has a Decline button + dialog, and a `declined` phase — Task 11 embeds it.

**Design note (deviation from spec wording):** instead of extracting a separate `SigningForm` component, `SignView.vue` itself is the shared signing component — the internal route keeps using it directly, and the external view (Task 11) mounts it as a child after verification. Same isolation goal, far less churn.

- [ ] **Step 1: Update `types.ts`**

```ts
// User + UserBrief: add
  is_external: boolean;

// SubmitterStatus / SubmissionStatus / AuditEventType: add "declined" to each union.

// SignerViewOut: add
  /** The signer's display name (rendered into `name` fields). */
  my_name: string;

// New shapes:
export interface SignTokenViewOut {
  status: "open" | "already_signed" | "completed" | "cancelled" | "declined";
  title: string;
  sender_name: string;
  masked_email: string;
}
```

- [ ] **Step 2: Update `labels.ts`**

In `signerStatusLabel`: before the fallback, `if (status === "declined") return "Declined";`. In `signerStatusColor`: `if (status === "declined") return "error";`. In `envelopeStatusLabel`: `if (status === "declined") return "Declined";`. In `envelopeStatusColor`: `if (status === "declined") return "error";`.

- [ ] **Step 3: Update `SignView.vue`**

1. Props: `const props = defineProps<{ submitterId: string; external?: boolean }>();`
2. Remove `useAuthStore` import/usage; replace the name-slot (`{{ auth.me?.name }}`) with `{{ view?.my_name }}`.
3. Every `http.get`/`http.post` in this file gets `skipAuthRedirect: props.external === true` merged into its config (for blob requests: `{ responseType: "blob", skipAuthRedirect: props.external === true }`), so an expired signer cookie surfaces as an inline error, never a bounce to `/login`.
4. Phase union gains `"declined"`. Blocked-state message: in `load()`, when `signRes.data.submission.status === "declined"` set `blockedReason.value = "This envelope was declined and is no longer active."` (check before the generic non-pending branch).
5. Success/blocked cards: wrap the `Back to home` button in `v-if="!props.external"`; when external, show `<p class="text-medium-emphasis">You can close this window.</p>` instead.
6. Decline UI:
   - State: `const declineOpen = ref(false); const declineReason = ref(""); const declining = ref(false);`
   - Dock: add before the Finish button:

```html
<v-btn variant="text" color="error" class="mr-2" @click="declineOpen = true">Decline</v-btn>
```

   - Dialog (sibling of the review dialog):

```html
<v-dialog v-model="declineOpen" max-width="480">
  <v-card>
    <v-card-title>Decline to sign?</v-card-title>
    <v-card-text>
      <p class="mb-3">This voids the envelope for everyone. The sender will be notified.</p>
      <v-textarea v-model="declineReason" label="Reason (optional)" rows="3" counter="500" maxlength="500" />
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn variant="text" @click="declineOpen = false">Keep signing</v-btn>
      <v-btn color="error" variant="flat" :loading="declining" @click="decline">Decline</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>
```

   - Handler:

```ts
async function decline(): Promise<void> {
  declining.value = true;
  errorMessage.value = null;
  try {
    await http.post(
      `/sign/${props.submitterId}/decline`,
      { reason: declineReason.value.trim() || null },
      { skipAuthRedirect: props.external === true },
    );
    declineOpen.value = false;
    phase.value = "declined";
  } catch (err) {
    errorMessage.value = extractError(err);
    declineOpen.value = false;
  } finally {
    declining.value = false;
  }
}
```

   - Declined card (after the success card):

```html
<v-card v-else-if="phase === 'declined'" class="state-card" variant="flat" border>
  <v-card-text class="text-center py-8">
    <v-icon icon="mdi-close-octagon-outline" size="56" color="error" class="mb-3" aria-hidden="true" />
    <p class="text-h5 mb-1">You declined to sign.</p>
    <p class="text-medium-emphasis">The sender has been notified.</p>
    <p v-if="external" class="text-medium-emphasis mt-4 mb-0">You can close this window.</p>
    <div v-else class="mt-4">
      <v-btn variant="text" :to="{ name: 'dashboard' }" prepend-icon="mdi-home">Back to home</v-btn>
    </div>
  </v-card-text>
</v-card>
```

- [ ] **Step 4: Update `EnvelopeDetailView.vue`**

In the event-text `switch`, add `case "declined": return \`Declined by ${event.actor?.name ?? "someone"}${event.detail?.reason ? ` — "${event.detail.reason}"` : ""}\`;`. Add `declined: "mdi-close-octagon"` to `EVENT_ICONS`. In the timeline `:dot-color` ternary, treat `declined` like `cancelled` (error color).

- [ ] **Step 5: Type-check**

Run: `cd frontend && npx vue-tsc --noEmit` — Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/utils/labels.ts frontend/src/views/SignView.vue frontend/src/views/EnvelopeDetailView.vue
git commit -m "feat: declined status UI and SignView external/decline support"
```

---

### Task 11: Frontend — ExternalSignView + public route

**Files:**
- Create: `frontend/src/views/ExternalSignView.vue`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: token endpoints (Task 5), `SignView` with `external` prop (Task 10), `SignTokenViewOut` type.
- Produces: public route `/sign/t/:accessUid` (name `sign-external`).

- [ ] **Step 1: Add the route** (`router/index.ts`, before the `/sign/:submitterId` entry for readability — path shapes don't collide)

```ts
  {
    path: "/sign/t/:accessUid",
    name: "sign-external",
    component: () => import("../views/ExternalSignView.vue"),
    props: true,
    // External signers have no session — access is proven by the emailed
    // token + verification code, not by login.
    meta: { public: true },
  },
```

- [ ] **Step 2: Create `ExternalSignView.vue`**

```vue
<script setup lang="ts">
/**
 * External signer entry: /sign/t/{accessUid}. Flow: landing (envelope title +
 * masked email) -> emailed 6-digit code -> the shared SignView (external
 * mode), authorized by the scoped sign_signer cookie the verify call set.
 * All requests skipAuthRedirect: there is no login to bounce to.
 */
import { onMounted, ref } from "vue";
import axios from "axios";
import http, { extractError } from "../utils/http";
import SignView from "./SignView.vue";
import type { SignTokenViewOut } from "../types";

const props = defineProps<{ accessUid: string }>();

type Phase = "loading" | "error" | "landing" | "code" | "signing" | "closed";

const phase = ref<Phase>("loading");
const view = ref<SignTokenViewOut | null>(null);
const errorMessage = ref<string | null>(null);
const codeError = ref<string | null>(null);
const code = ref("");
const sending = ref(false);
const verifying = ref(false);
const submitterId = ref<number | null>(null);

const CLOSED_MESSAGES: Record<string, string> = {
  already_signed: "You've already signed this document.",
  completed: "Everyone has signed — this envelope is complete.",
  cancelled: "This envelope was cancelled by the sender.",
  declined: "This envelope was declined and is no longer active.",
};

async function load(): Promise<void> {
  phase.value = "loading";
  try {
    const { data } = await http.get<SignTokenViewOut>(`/sign/token/${props.accessUid}`, { skipAuthRedirect: true });
    view.value = data;
    phase.value = data.status === "open" ? "landing" : "closed";
  } catch (err) {
    errorMessage.value =
      axios.isAxiosError(err) && err.response?.status === 404
        ? "This signing link isn't valid. Check that you opened the full link from your email."
        : extractError(err);
    phase.value = "error";
  }
}

onMounted(load);

async function requestCode(): Promise<void> {
  sending.value = true;
  codeError.value = null;
  try {
    await http.post(`/sign/token/${props.accessUid}/request-code`, null, { skipAuthRedirect: true });
    phase.value = "code";
  } catch (err) {
    codeError.value = extractError(err);
    if (phase.value === "landing") phase.value = "code";
  } finally {
    sending.value = false;
  }
}

async function verify(): Promise<void> {
  if (!code.value.trim()) return;
  verifying.value = true;
  codeError.value = null;
  try {
    const { data } = await http.post<{ submitter_id: number }>(
      `/sign/token/${props.accessUid}/verify`,
      { code: code.value.trim() },
      { skipAuthRedirect: true },
    );
    submitterId.value = data.submitter_id;
    phase.value = "signing";
  } catch (err) {
    codeError.value = extractError(err);
    code.value = "";
  } finally {
    verifying.value = false;
  }
}
</script>

<template>
  <SignView v-if="phase === 'signing' && submitterId != null" :submitter-id="String(submitterId)" external />

  <v-container v-else class="external-sign">
    <v-progress-linear v-if="phase === 'loading'" indeterminate class="mb-4" />

    <v-alert v-else-if="phase === 'error'" type="error">{{ errorMessage }}</v-alert>

    <v-card v-else-if="phase === 'closed' && view" class="state-card" variant="flat" border>
      <v-card-text class="text-center py-8">
        <v-icon icon="mdi-file-lock-outline" size="48" class="mb-3 text-medium-emphasis" aria-hidden="true" />
        <p class="text-h6 mb-1">{{ CLOSED_MESSAGES[view.status] }}</p>
        <p class="text-medium-emphasis mb-0">You can close this window.</p>
      </v-card-text>
    </v-card>

    <v-card v-else-if="view" class="state-card" variant="flat" border>
      <v-card-text class="py-8 px-6">
        <p class="text-overline mb-1">Signature requested</p>
        <h1 class="text-h5 mb-2">{{ view.title }}</h1>
        <p class="text-medium-emphasis mb-6">
          {{ view.sender_name }} at Pumasi has requested your signature.
        </p>

        <template v-if="phase === 'landing'">
          <p class="mb-4">
            To verify it's you, we'll email a 6-digit code to <strong>{{ view.masked_email }}</strong>.
          </p>
          <v-btn color="primary" variant="flat" :loading="sending" @click="requestCode">Email me a code</v-btn>
        </template>

        <template v-else>
          <p class="mb-4">
            Enter the 6-digit code we sent to <strong>{{ view.masked_email }}</strong>. It expires in 10 minutes.
          </p>
          <v-alert v-if="codeError" type="error" density="compact" class="mb-4">{{ codeError }}</v-alert>
          <v-otp-input v-model="code" length="6" class="mb-4" @finish="verify" />
          <div class="d-flex align-center">
            <v-btn color="primary" variant="flat" :loading="verifying" :disabled="code.length < 6" @click="verify">
              Verify &amp; continue
            </v-btn>
            <v-btn variant="text" class="ml-2" :loading="sending" @click="requestCode">Resend code</v-btn>
          </div>
        </template>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<style scoped>
.external-sign {
  max-width: 640px;
}

.state-card {
  margin-top: 48px;
}
</style>
```

(No `App.vue` change needed: with no session, the app bar already renders only the logo + feedback button.)

- [ ] **Step 3: Type-check + build**

Run: `cd frontend && npx vue-tsc --noEmit && npm run build` — Expected: clean. (If `v-otp-input` is unavailable in the installed Vuetify version, substitute a plain `v-text-field` with `maxlength="6"` and `inputmode="numeric"`.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/ExternalSignView.vue frontend/src/router/index.ts
git commit -m "feat: public external signing page with code verification"
```

---

### Task 12: Frontend — send wizard external add + admin users chips

**Files:**
- Modify: `frontend/src/views/SendView.vue`, `frontend/src/views/AdminUsersView.vue`

**Interfaces:**
- Consumes: `POST /api/users` 422 detail `"External signer requires a name"` (Task 2), `User.is_external`.

- [ ] **Step 1: SendView — name dialog for new external emails**

State (near the other adhoc refs):

```ts
const externalNameOpen = ref(false);
const externalName = ref("");
const pendingExternal = ref<{ index: number; email: string } | null>(null);
```

In `onPickAdhocRecipient`, replace the `catch` block of the `POST /users` call:

```ts
  try {
    const { data } = await http.post<User>("/users", { email });
    if (!users.value.some((u) => u.id === data.id)) users.value.push(data);
    assignRecipient(index, data);
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.data?.detail === "External signer requires a name") {
      pendingExternal.value = { index, email };
      externalName.value = "";
      externalNameOpen.value = true;
      return;
    }
    recipientError.value = extractError(err);
  }
```

(add `import axios from "axios";` if not present). Add the confirm handler:

```ts
async function addExternalSigner(): Promise<void> {
  if (!pendingExternal.value || !externalName.value.trim()) return;
  try {
    const { data } = await http.post<User>("/users", {
      email: pendingExternal.value.email,
      name: externalName.value.trim(),
    });
    if (!users.value.some((u) => u.id === data.id)) users.value.push(data);
    assignRecipient(pendingExternal.value.index, data);
    externalNameOpen.value = false;
    pendingExternal.value = null;
  } catch (err) {
    recipientError.value = extractError(err);
    externalNameOpen.value = false;
  }
}
```

Dialog (near the wizard's other dialogs):

```html
<v-dialog v-model="externalNameOpen" max-width="440">
  <v-card>
    <v-card-title>Add external signer</v-card-title>
    <v-card-text>
      <p class="mb-3">
        <strong>{{ pendingExternal?.email }}</strong> is outside Pumasi. Their name appears on the
        signed document and certificate, so enter it exactly.
      </p>
      <v-text-field v-model="externalName" label="Full name" autofocus @keyup.enter="addExternalSigner" />
    </v-card-text>
    <v-card-actions>
      <v-spacer />
      <v-btn variant="text" @click="externalNameOpen = false">Cancel</v-btn>
      <v-btn color="primary" variant="flat" :disabled="!externalName.trim()" @click="addExternalSigner">Add signer</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>
```

- [ ] **Step 2: SendView — "External" chips**

Where `userItems`' `display` string is built (search for `display:`), append ` · external` for external users, e.g. `display: u.is_external ? \`${userLabel(u)} · external\` : userLabel(u)`. In the review-step signer list (line ~705 area), after the signer name add:

```html
<v-chip v-if="isExternalUser(...)" size="x-small" color="warning" variant="tonal" class="ml-2">External</v-chip>
```

implemented with a small helper `function isExternalId(userId: number | null): boolean { return users.value.find((u) => u.id === userId)?.is_external ?? false; }` wired to whichever id that row displays (`roleAssignments[role]` in template mode, `adhocRecipients[i]` in ad-hoc mode).

- [ ] **Step 3: AdminUsersView — external chip + no admin toggle**

Headers: insert `{ title: "Type", key: "is_external", sortable: false }` before Admin. Template slots:

```html
<template #item.is_external="{ item }">
  <v-chip v-if="item.is_external" size="small" color="warning" variant="tonal">External</v-chip>
  <span v-else class="text-medium-emphasis">Employee</span>
</template>
```

and in the existing admin-switch slot, extend `:disabled` with `|| item.is_external` and the `:title` with an external-user explanation (`item.is_external ? "External signers cannot be admins" : ...`).

- [ ] **Step 4: Type-check + commit**

Run: `cd frontend && npx vue-tsc --noEmit` — Expected: clean.

```bash
git add frontend/src/views/SendView.vue frontend/src/views/AdminUsersView.vue
git commit -m "feat: add external signers from the send wizard"
```

---

### Task 13: Dev hooks + e2e coverage

**Files:**
- Modify: `backend/app/routers/submissions.py` (dev-signing-links)
- Create: `frontend/e2e/external-sign-flow.spec.ts`
- Test: `backend/tests/test_external_signing.py` (dev-route gating)

**Interfaces:**
- Produces: `GET /api/submissions/{id}/dev-signing-links` — admin + `DEV_AUTH_BYPASS` only (404 otherwise), returns `[{"submitter_id": int, "access_uid": str | null}]`. `dev_code` already exists in request-code (Task 5).

- [ ] **Step 1: Backend test** (append to `backend/tests/test_external_signing.py`)

```python
def test_dev_signing_links_gated_by_bypass(admin_client, make_client, db, monkeypatch, tmp_path) -> None:
    _capture_mail(monkeypatch)
    submission, access_uid, submitter_id = _external_submission(admin_client, db)

    resp = admin_client.get(f"/api/submissions/{submission['id']}/dev-signing-links")
    assert resp.status_code == 200
    assert resp.json() == [{"submitter_id": submitter_id, "access_uid": access_uid}]

    prod_settings = Settings(session_secret="test-session-secret", app_base_url="http://testserver", data_dir=str(tmp_path))
    prod_client = make_client(prod_settings)
    assert prod_client.get(f"/api/submissions/{submission['id']}/dev-signing-links").status_code in (401, 404)
```

- [ ] **Step 2: Implement the route** (in `submissions.py`, after `remind_submission`)

```python
@router.get("/{submission_id}/dev-signing-links")
def dev_signing_links(
    submission_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _admin: User = Depends(require_admin),
) -> list[dict]:
    """Dev/e2e-only: each submitter's access_uid. 404s (like dev-login) unless
    DEV_AUTH_BYPASS — tests can't read the signer's mailbox for the link."""
    if not settings.dev_auth_bypass:
        raise HTTPException(status_code=404)
    submission = db.scalars(_submission_query().where(Submission.id == submission_id)).one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return [{"submitter_id": s.id, "access_uid": s.access_uid} for s in submission.submitters]
```

Run: `cd backend && PY -m pytest tests/test_external_signing.py -v` — Expected: PASS.

- [ ] **Step 3: Write the e2e spec** — first skim `frontend/e2e/sign-flow.spec.ts` and reuse its signature-drawing and template/submission setup helpers verbatim where they exist (drawing on the SignaturePad canvas especially). The spec below is the shape; align selectors with what sign-flow.spec.ts actually uses:

```ts
// frontend/e2e/external-sign-flow.spec.ts
import * as fs from "node:fs";
import { expect, test } from "@playwright/test";
import { FIXTURE_PDF, devLogin, waitForPdfRendered } from "./helpers";

const FIELDS = [
  { id: "sig1", type: "signature", role: "Signer 1", page: 0, x: 0.1, y: 0.1, w: 0.25, h: 0.06, required: true },
];

async function createExternalEnvelope(context: import("@playwright/test").BrowserContext, title: string) {
  const user = await (await context.request.post("/api/users", { data: { email: "ext@vendor.com", name: "Ext Vendor" } })).json();
  const tpl = await (
    await context.request.post("/api/templates", {
      multipart: {
        name: title,
        file: { name: "sample.pdf", mimeType: "application/pdf", buffer: fs.readFileSync(FIXTURE_PDF) },
      },
    })
  ).json();
  await context.request.put(`/api/templates/${tpl.id}/fields`, { data: { fields: FIELDS } });
  const submission = await (
    await context.request.post("/api/submissions", {
      data: { template_id: tpl.id, title, signers: [{ role: "Signer 1", user_id: user.id }] },
    })
  ).json();
  const links = await (await context.request.get(`/api/submissions/${submission.id}/dev-signing-links`)).json();
  return { submission, accessUid: links[0].access_uid as string };
}

test("external signer verifies by code and signs", async ({ browser }) => {
  const admin = await browser.newContext();
  await devLogin(admin, "admin@pumasi.ai", "Admin");
  const { submission, accessUid } = await createExternalEnvelope(admin, "External e2e");

  const signer = await browser.newContext(); // no login
  const page = await signer.newPage();
  await page.goto(`/sign/t/${accessUid}`);
  await expect(page.getByText("e***@vendor.com")).toBeVisible();
  await page.getByRole("button", { name: "Email me a code" }).click();

  // No mailbox in e2e: request a fresh code via the API (DEV_AUTH_BYPASS
  // exposes it as dev_code) — this replaces the one the click just sent.
  const codeRes = await (await signer.request.post(`/api/sign/token/${accessUid}/request-code`)).json();
  await page.locator(".v-otp-input input").first().fill(codeRes.dev_code);
  await page.getByRole("button", { name: /verify/i }).click();

  await waitForPdfRendered(page);
  await page.getByRole("button", { name: /click to sign/i }).click();
  // Draw on the signature pad — mirror sign-flow.spec.ts's drawing steps here.
  const canvas = page.locator(".signature-pad canvas, canvas").last();
  const box = (await canvas.boundingBox())!;
  await page.mouse.move(box.x + 30, box.y + 40);
  await page.mouse.down();
  await page.mouse.move(box.x + 160, box.y + 70, { steps: 10 });
  await page.mouse.up();
  await page.getByRole("button", { name: /save|use signature|apply/i }).click();

  await page.getByRole("button", { name: "Finish" }).click();
  await page.getByLabel(/legally binding/i).check();
  await page.getByRole("button", { name: /sign & finish/i }).click();
  await expect(page.getByText("Thanks — your part is done.")).toBeVisible();
  await expect(page.getByText("You can close this window.")).toBeVisible();

  const detail = await (await admin.request.get(`/api/submissions/${submission.id}`)).json();
  expect(detail.status).toBe("completed");
});

test("external signer declines with a reason", async ({ browser }) => {
  const admin = await browser.newContext();
  await devLogin(admin, "admin@pumasi.ai", "Admin");
  const { submission, accessUid } = await createExternalEnvelope(admin, "Decline e2e");

  const signer = await browser.newContext();
  const page = await signer.newPage();
  await page.goto(`/sign/t/${accessUid}`);
  await page.getByRole("button", { name: "Email me a code" }).click();
  const codeRes = await (await signer.request.post(`/api/sign/token/${accessUid}/request-code`)).json();
  await page.locator(".v-otp-input input").first().fill(codeRes.dev_code);
  await page.getByRole("button", { name: /verify/i }).click();
  await waitForPdfRendered(page);

  await page.getByRole("button", { name: "Decline" }).click();
  await page.getByLabel(/reason/i).fill("Wrong entity");
  await page.getByRole("button", { name: "Decline", exact: true }).last().click();
  await expect(page.getByText("You declined to sign.")).toBeVisible();

  const detail = await (await admin.request.get(`/api/submissions/${submission.id}`)).json();
  expect(detail.status).toBe("declined");
});
```

- [ ] **Step 4: Run e2e locally** per the memory recipe (uvicorn on :8080 + fresh `pumasi_sign_e2e_local` DB, `DEV_AUTH_BYPASS=1`; see `.github/workflows/ci.yaml` e2e job for env):

Run: `cd frontend && npx playwright test e2e/external-sign-flow.spec.ts`
Expected: 2 passed. Fix selectors against the real DOM as needed — the assertions (completed/declined status via API) are the contract.

- [ ] **Step 5: Lint + commit**

```bash
git add backend/app/routers/submissions.py backend/tests/test_external_signing.py frontend/e2e/external-sign-flow.spec.ts
git commit -m "test: e2e external signing and decline flows with dev hooks"
```

---

### Task 14: Docs + full verification

**Files:**
- Modify: `README.md` (line 4 area), `CLAUDE.md` (line 3 description)

- [ ] **Step 1: Update the "internal only" wording**

Both files describe the app as internal-only / "not for external parties". Update to: internal e-signature service for Pumasi employees; **external recipients can sign via emailed token links + email verification codes** but can never log in or send. Keep it to one sentence each.

- [ ] **Step 2: Full verification suite**

```bash
cd backend && PY -m ruff check . && PY -m ruff format --check . && PY -m pytest
cd ../frontend && npx vue-tsc --noEmit && npm run build && npx playwright test
```

Expected: all green (docx/xlsx conversion tests may auto-skip without LibreOffice; e2e needs the app running per the local recipe).

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: external signers are now supported recipients"
```

---

## Self-review notes

- **Spec coverage:** data model → T1; provisioning + guards → T2/T3; token flow → T4/T5; endpoint/file reuse → T6/T7; links + completion email → T8; decline → T9; frontend → T10-T12; security (hashing, attempts, rate limits, scoped cookie, masked email) → T4/T5/T6/T7; testing → every task + T13; docs → T14.
- **Known deviation:** SignView is reused as the shared signing component instead of extracting `SigningForm` (noted in T10).
- **Ordering quirk:** access_uid generation was pulled from T8 into T5 step 3.4 so T5's tests pass standalone; T8 only touches notifications.
