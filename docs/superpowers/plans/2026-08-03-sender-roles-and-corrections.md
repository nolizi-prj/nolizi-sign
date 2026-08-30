# Sender Roles & Envelope Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Pumasi user can send envelopes by default (admin-revocable per user); senders/admins can correct pending envelopes (title, message, external signer contact info, replace a signer); the send wizard never creates signers from partially-typed emails; the feedback dialog accepts pasted screenshots.

**Architecture:** One new `users.can_send` flag + a `require_sender` FastAPI dependency replaces `require_admin` on send-path routes. Correction endpoints: `PATCH /api/submissions/{id}`, extended `PUT /api/users/{id}`, new `PUT /api/submissions/{id}/submitters/{sid}` — all recording a new `corrected` audit event. Frontend: store-level `canSend` gating, an explicit add-signer dialog in SendView, correction dialogs in EnvelopeDetailView, paste handler in FeedbackDialog.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, pytest (Postgres :5433), Vue 3 + Vuetify 3 + TypeScript (`vue-tsc`).

**Spec:** `docs/superpowers/specs/2026-08-03-sender-roles-and-corrections-design.md` (approved)

## Global Constraints

- Tests are Postgres-only via `TEST_DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`). Worktree has no venv — use `/home/m/dev/pumasi-sign/backend/.venv/Scripts/python.exe -m pytest ...` from `backend/`.
- Alembic head before this plan: run `alembic heads` first; chain the two new migrations linearly (Task 1's revises the current head; Task 3's revises Task 1's).
- `require_sender` passes iff `user.is_admin or (user.can_send and not user.is_external)`.
- Correction endpoints: envelope creator or admin only; envelope must be `pending`; every correction records audit event `corrected` with a `detail` dict naming what changed (for signer/contact changes: from/to user ids and emails).
- Replace-signer MUST regenerate `access_uid` for an external replacement and null it for an internal one — the old emailed link must stop working.
- Internal (pumasi.ai / ALLOWED_EMAIL_DOMAINS) users' emails are immutable (SSO matches by email). Contact edits apply to `is_external` users only.
- Email regex everywhere (backend `UserCreate`/`UserUpdate`, frontend `EMAIL_PATTERN`): require 2+ char TLD: `[^@\s]+@[^@\s]+\.[^@\s]{2,}`.
- Frontend checks: `npx vue-tsc --noEmit` and `npm run build` from `frontend/` must pass.
- Lint before every commit: `ruff check . && ruff format .` from `backend/`.
- Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Known environmental flake (never yours to fix): `test_submitter_out_includes_reminder_fields` (Docker clock skew).

---

### Task 1: `can_send` flag, `require_sender`, `/me` exposure

**Files:**
- Modify: `backend/app/models.py` (User, after `is_external` ~line 41)
- Modify: `backend/app/auth.py` (after `require_admin`, ~line 163)
- Modify: `backend/app/schemas.py` (`UserOut`, ~line 122)
- Modify: `backend/app/routers/auth.py` (`me`, ~line 143; the dict at ~line 74 is the login response — update it too if it mirrors `/me`'s shape)
- Create: `backend/migrations/versions/b2e7d4a1c8f3_user_can_send.py` (down_revision = current `alembic heads` output)
- Test: `backend/tests/test_auth.py` (append), `backend/tests/test_users.py` (existing suite must stay green)

**Interfaces:**
- Produces: `User.can_send: Mapped[bool]` (server_default `"true"`); `auth.require_sender(user: User = Depends(current_user)) -> User` raising 403 `"Sender access required"`; `UserOut.can_send: bool`; `/api/auth/me` response gains `"can_send": bool` — the EFFECTIVE value `user.is_admin or (user.can_send and not user.is_external)`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_auth.py`; follow that file's existing dev-login fixture conventions — read it first):

```python
def test_me_reports_effective_can_send(make_client, app_settings) -> None:
    client = make_client(app_settings)
    client.post("/api/auth/dev-login", json={"email": "sender@pumasi.ai", "name": "Sender"})
    assert client.get("/api/auth/me").json()["can_send"] is True


def test_require_sender_blocks_revoked_user(make_client, app_settings, db) -> None:
    client = make_client(app_settings)
    client.post("/api/auth/dev-login", json={"email": "norights@pumasi.ai", "name": "No Rights"})
    from app.models import User
    user = db.query(User).filter_by(email="norights@pumasi.ai").one()
    user.can_send = False
    db.commit()
    # GET /api/templates is sender-gated after Task 2; here use a probe that
    # exercises the dependency directly once Task 2 lands. For THIS task,
    # assert the model default + /me effective logic instead:
    assert client.get("/api/auth/me").json()["can_send"] is False
```

Plus a pure-unit test of the dependency (no HTTP; FastAPI deps here are plain functions, mirroring how `require_admin` is written): call `require_sender(User(is_admin=..., can_send=..., is_external=...))` directly and assert: admin with `can_send=False` → returned; internal `can_send=True` → returned; internal `can_send=False` → raises 403 `HTTPException`; external `can_send=True` → raises 403.

- [ ] **Step 2: Run tests, verify RED** (`-k "can_send or require_sender"`; expect AttributeError/KeyError)
- [ ] **Step 3: Implement** — model column (comment: send permission, admin-revocable; external users excluded in the guard, not the column); `require_sender` mirroring `require_admin`'s shape; `UserOut.can_send`; `/me` effective value; migration (`op.add_column("users", sa.Column("can_send", sa.Boolean(), nullable=False, server_default="true"))`, symmetric downgrade).
- [ ] **Step 4: Run tests, verify GREEN**; run `tests/test_auth.py tests/test_users.py` fully.
- [ ] **Step 5: Lint, commit** `feat: user can_send flag and require_sender guard`.

---

### Task 2: Re-gate send-path routes to `require_sender`

**Files:**
- Modify: `backend/app/routers/submissions.py` (create ~183, adhoc merged-document ~215, adhoc create ~255: swap `Depends(require_admin)` → `Depends(require_sender)`; rename the `admin` param to `sender` and update usages in those bodies)
- Modify: `backend/app/routers/templates.py` (all `require_admin` → `require_sender`, param renames)
- Modify: `backend/app/routers/users.py` (`list_users`, `create_user` → `require_sender`; `update_user` stays `require_admin` in this task)
- Test: `backend/tests/test_submissions.py`, `backend/tests/test_templates.py`, `backend/tests/test_users.py` (append)

**Interfaces:**
- Consumes: `require_sender` (Task 1).
- Produces: non-admin senders can create templates/submissions and list/provision users; `can_send=false` internal users get 403 on those routes.

- [ ] **Step 1: Write failing tests.** One per router, following each file's existing client fixture pattern (most use `admin_client`; add a `sender_client`-style helper via dev-login with a non-admin pumasi email):

```python
def test_plain_pumasi_user_can_list_users(make_client, app_settings) -> None:
    client = make_client(app_settings)
    client.post("/api/auth/dev-login", json={"email": "plain@pumasi.ai", "name": "Plain"})
    assert client.get("/api/users").status_code == 200


def test_revoked_user_cannot_create_template(...)  # dev-login, flip can_send False via db fixture, POST /api/templates upload -> 403
def test_plain_pumasi_user_can_create_submission(...)  # non-admin sender runs the existing create-submission arrange used by admin tests -> 201
```

Write all three fully by copying the nearest existing test's arrange code in each file.

- [ ] **Step 2: RED** (403s where 200/201 expected).
- [ ] **Step 3: Swap the dependencies + param renames.** Grep both routers afterward: zero `require_admin` left in `templates.py`; `submissions.py` keeps it ONLY on `dev_signing_links`; `users.py` keeps it ONLY on `update_user`.
- [ ] **Step 4: GREEN** — run the three test files fully (regression: admin flows must still pass).
- [ ] **Step 5: Lint, commit** `feat: open sending, templates, and the signer picker to all senders`.

---

### Task 3: `corrected` audit event + PATCH title/message

**Files:**
- Modify: `backend/app/models.py` (`AUDIT_EVENTS` tuple ~line 25: append `"corrected"`)
- Create: `backend/migrations/versions/c9d1f6b3e2a7_audit_corrected_event.py` (revises Task 1's `b2e7d4a1c8f3`; upgrade = `op.drop_constraint("ck_audit_events_event", "audit_events")` + `op.create_check_constraint("ck_audit_events_event", "audit_events", "event IN ('created','sent','opened','signed','reminded','completed','cancelled','corrected')")`; downgrade recreates the old list)
- Modify: `backend/app/routers/submissions.py` (new PATCH route beside the existing detail route)
- Modify: `backend/app/schemas.py` (new `SubmissionPatch` with `title: str | None = None`, `message: str | None = None`, title validator: trimmed, non-empty, ≤255 when provided)
- Test: `backend/tests/test_submissions.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `PATCH /api/submissions/{id}` body `{title?, message?}` → 200 `SubmissionOut`; 403 non-creator non-admin; 409 non-pending; records `audit.record(db, id, "corrected", actor_user_id=user.id, ip=..., detail={"changed": [...]})` — check `audit.record`'s actual signature first (it may not take `detail`; if not, extend it with an optional `detail` param defaulting to None, keeping existing callers valid).

- [ ] **Step 1: Failing tests:** creator edits title+message → 200, new values in response, audit list (`GET /api/submissions/{id}/audit` — existing route) contains a `corrected` event; another non-admin sender → 403; admin (non-creator) → 200; completed envelope → 409; empty title → 422. Copy the arrange from existing submission-detail tests.
- [ ] **Step 2: RED** (405 Method Not Allowed initially).
- [ ] **Step 3: Implement** route (creator-or-admin guard like `cancel_submission`'s pre-checks; only touch fields present in payload; no-op patch with neither field → 422). Update the module docstring list of routes if one exists.
- [ ] **Step 4: GREEN** + full `tests/test_submissions.py`.
- [ ] **Step 5: Lint, commit** `feat: senders can correct a pending envelope's title and message`.

---

### Task 4: Contact correction via `PUT /api/users/{id}` + stricter email regex

**Files:**
- Modify: `backend/app/schemas.py` (`UserUpdate` becomes all-optional: `is_admin: bool | None = None`, `name: str | None = None`, `email: str | None = None`, `can_send: bool | None = None`; email validator = `UserCreate`'s normalize + NEW 2+ char TLD regex `[^@\s]+@[^@\s]+\.[^@\s]{2,}`; apply the same tightened regex to `UserCreate._normalize_email`, ~line 150)
- Modify: `backend/app/routers/users.py` (`update_user`: guard split — see below)
- Test: `backend/tests/test_users.py` (append)

**Interfaces:**
- Consumes: `require_sender` (Task 1).
- Produces: `update_user` authorization becomes two-tier: caller resolved via `require_sender`; if payload touches `is_admin` or `can_send` → caller must be admin (403 otherwise; keep the existing self-demotion 409); if payload touches `name`/`email` → target user must be `is_external` (403 `"Only external users' contact info can be edited"`), new email must be unique (409) and NOT internal-domain (`email_domain_allowed` → 422 `"Use an external email address"`).

- [ ] **Step 1: Failing tests:** sender corrects external user's email `...@gmail.co`→`...@gmail.com` → 200 + persisted; sender edits internal user's name → 403; new email colliding with existing user → 409; internal-domain email on external user → 422; sender toggling `is_admin` → 403; admin toggling `can_send` → 200; `POST /users` with 1-char TLD (`x@y.c`) → 422 (regex tightening); existing admin-toggle tests still green.
- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** (update the route + module docstrings, which currently say "admin-only"; `exclude_unset=True` to distinguish "absent" from "null").
- [ ] **Step 4: GREEN** + full `tests/test_users.py`.
- [ ] **Step 5: Lint, commit** `feat: correct external signer contact info; tighten email validation`.

---

### Task 5: Replace a signer

**Files:**
- Modify: `backend/app/routers/submissions.py` (new route), `backend/app/schemas.py` (`SubmitterReplace { user_id: int }`)
- Check first: how `access_uid` is generated at submission creation (grep `access_uid` in `submissions.py`/`auth.py` — reuse the same generator) and how the per-submitter sign-request email is sent inside `notifications.on_submission_created` (extract a `send_sign_request(db, submitter, submission, settings)` helper if one doesn't exist, refactoring `on_submission_created` to call it per submitter — behavior-preserving, existing notification tests must stay green).
- Test: `backend/tests/test_submissions.py` (append)

**Interfaces:**
- Consumes: `require_sender`, `corrected` audit event, `SubmitterReplace`.
- Produces: `PUT /api/submissions/{id}/submitters/{submitter_id}` → 200 `SubmissionOut`. Rules: creator-or-admin; submission `pending` (409); target submitter not `completed` (409 `"Signer already signed"`); `user_id` must exist (404) and not already be a submitter on this envelope (409). Effects: `submitter.user_id` swapped; `status="pending"`; `values={}`; `signed_at=None`; `ip_address=None`; `last_reminded_at=None`; `reminder_count=0`; `access_uid` = fresh value if new user is external else `None`; sign-request email sent to the new signer (sets `email_status`); `corrected` audit event with detail `{"submitter_id": sid, "from": {"user_id":..., "email":...}, "to": {"user_id":..., "email":...}}`.

- [ ] **Step 1: Failing tests:** replace pending signer with another internal user → 200, submitter row shows new user, reset fields, audit `corrected` present; old external `access_uid` no longer resolves (`GET` the external sign URL/route used in existing external-signer tests → 404); external replacement gets a NEW non-null `access_uid` different from the old one; completed submitter → 409; duplicate user → 409; non-creator sender → 403. Mirror arranges from existing external-signer tests (find them in `test_signing.py`/`test_submissions.py` — grep `access_uid`).
- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement** (route + the notifications helper extraction).
- [ ] **Step 4: GREEN** + full `tests/test_submissions.py tests/test_notifications.py tests/test_signing.py`.
- [ ] **Step 5: Lint, commit** `feat: replace a signer on a pending envelope`.

---

### Task 6: Frontend — canSend gating + admin toggle

**Files:**
- Modify: `frontend/src/types.ts` (`Me`/`User` types: add `can_send: boolean`)
- Modify: `frontend/src/store/auth.ts` (add `canSend` computed off `me.value?.can_send`, export it beside `isAdmin` line 18/38)
- Modify: `frontend/src/App.vue` (Send nav button ~line 36: `v-if="auth.isAdmin"` → `v-if="auth.canSend"`; Users button stays `isAdmin`)
- Modify: `frontend/src/views/DashboardView.vue` (send/template affordances gated `auth.isAdmin` ~lines 80/83/308 → `auth.canSend`; the templates fetch too)
- Modify: `frontend/src/views/AdminUsersView.vue` (new "Can send" column with a `v-switch` mirroring the `is_admin` toggle pattern at lines 37–45/74–79, PUTs `{can_send: value}`; switch disabled for `item.is_external` rows with a tooltip "External signers cannot send")

**Interfaces:**
- Consumes: `/me.can_send` (Task 1), `PUT /users/{id}` accepting `can_send` (Task 4).

- [ ] **Step 1: Implement** the five edits (no component tests in this repo — the gate is `vue-tsc`).
- [ ] **Step 2: Verify:** `npx vue-tsc --noEmit` and `npm run build` from `frontend/` pass.
- [ ] **Step 3: Commit** `feat: gate send UI on can_send; admin toggle for send rights`.

---

### Task 7: Frontend — safe signer entry (SendView)

**Files:**
- Modify: `frontend/src/views/SendView.vue`

**Interfaces:**
- Consumes: `POST /users` (unchanged API).
- Behavior contract (replaces the silent-create path at lines 290–352):
  1. `EMAIL_PATTERN` (line 264) → `/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/`.
  2. In `onPickAdhocRecipient`'s string branch: exact case-insensitive match to an existing user → `assignRecipient` (unchanged). Otherwise, for ANY other non-empty string (valid-looking or not), open the add-signer dialog (below) prefilled with the typed text — NEVER `http.post` from this handler. Remove the direct POST + 422-fallback logic (the dialog subsumes `pendingExternal`).
  3. Rework the existing `externalNameOpen` dialog into an "Add signer" dialog: editable `email` text field (prefilled) + `name` text field; live hint under email when it fails `EMAIL_PATTERN`; Confirm disabled until email valid (and name non-empty when the email's domain is NOT `pumasi.ai` — hardcode the same allowed-domain list source the backend reports? No: keep it simple, name is always optional in the UI and the backend's 422 "External signer requires a name" marks the name field required + shows the message — one round-trip, no duplicated domain logic).
  4. Confirm handler: POST `/users` `{email, name?}` → push to `users`, `assignRecipient`, close. 422 name-required → keep dialog open, mark name required. Other errors → `recipientError`, close.
  5. Dialog cancel leaves the row unchanged (null).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify** `npx vue-tsc --noEmit` + `npm run build`; run existing Playwright e2e if the app is running is NOT required here — CI's e2e job covers the send flow (it uses internal signers picked from the list, which still works).
- [ ] **Step 3: Commit** `fix: never create signers from partially typed emails; explicit add-signer dialog`.

---

### Task 8: Frontend — envelope correction UI

**Files:**
- Modify: `frontend/src/views/EnvelopeDetailView.vue`
- Modify: `frontend/src/types.ts` if the audit-event type union enumerates events (add `corrected`)

**Interfaces:**
- Consumes: `PATCH /api/submissions/{id}`, `PUT /api/users/{id}`, `PUT /api/submissions/{id}/submitters/{sid}` (Tasks 3–5).
- Behavior contract (read the view first; follow its existing dialog/action patterns — it already has cancel/remind actions):
  1. `canCorrect` computed: envelope `status === "pending"` and (`auth.isAdmin` or `me.id === envelope.created_by`).
  2. Title row: pencil icon (when `canCorrect`) → dialog with title + message fields prefilled → PATCH → refresh envelope. Show API errors in the dialog.
  3. Each signer row (when `canCorrect`): overflow menu (`mdi-dots-vertical`) with:
     - "Correct contact info…" — only for external signers, and only while that submitter isn't completed → dialog (name + email, prefilled) → `PUT /users/{userId}` → refresh. Surface 409/422 messages inline.
     - "Replace signer…" — only while that submitter isn't completed → dialog with the same combobox-style user picker pattern used in SendView (a simple `v-autocomplete` over `GET /users` is fine here) → `PUT /submissions/{id}/submitters/{sid}` → refresh.
  4. Audit timeline: render `corrected` events (label "Corrected", show `detail.changed` fields or from→to emails when present, matching how other events render).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify** `npx vue-tsc --noEmit` + `npm run build`.
- [ ] **Step 3: Commit** `feat: correct pending envelopes from the detail view`.

---

### Task 9: Frontend — feedback screenshot paste

**Files:**
- Modify: `frontend/src/components/FeedbackDialog.vue`

**Interfaces / behavior contract:**
1. `@paste.prevent` handler on the dialog's `v-card`: iterate `event.clipboardData?.items`, first item whose `type` is `image/png` or `image/jpeg` → `item.getAsFile()`; wrap in a named file when the browser gives a generic name: `new File([f], f.name && f.name !== "image.png" ? f.name : "pasted-screenshot.png", { type: f.type })`; assign to the existing `screenshot` ref (replacing any current selection). Non-image paste → ignore (let normal text paste through — so `.prevent` must apply ONLY when an image was consumed; use a plain handler that conditionally calls `event.preventDefault()`).
2. When `screenshotFile` is set (from paste OR file input), show a thumbnail preview (`URL.createObjectURL`, revoked on change/unmount) with a remove (×) button that clears `screenshot`.
3. Hint text under the input: "or paste a screenshot (Ctrl+V)".
4. Existing 3 MB validation & submit flow unchanged (the size check at line 33 already covers pasted files since it reads `screenshotFile`).

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Verify** `npx vue-tsc --noEmit` + `npm run build`.
- [ ] **Step 3: Commit** `feat: paste screenshots into the feedback dialog`.

---

### Task 10: Docs + full verification

**Files:**
- Modify: `CLAUDE.md` (Key facts: sending is sender-gated (`can_send`, default true for internal users, admin-revocable); corrections on pending envelopes by creator/admin)
- Modify: `README.md` only if it documents the admin-only sending anywhere (grep "admin" in README; update stale statements)

- [ ] **Step 1: Docs edits.**
- [ ] **Step 2: Full verification:** from `backend/`: `ruff check . && ruff format --check .`, full `pytest -q` (expect only the known clock-skew flake at worst; `alembic heads` must show exactly ONE head). From `frontend/`: `npx vue-tsc --noEmit`, `npm run build`.
- [ ] **Step 3: Commit** `docs: sender role and envelope correction notes`, push branch, and stop — the controller handles the PR.
