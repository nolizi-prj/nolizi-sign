# Pumasi Sign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Internal e-signature web service: admins place fields on uploaded documents, employees sign them, signed PDFs with audit pages are produced and emailed.

**Architecture:** Single FastAPI service serving a JSON API under `/api` plus the built Vue 3 SPA as static files; PostgreSQL for state, a mounted volume for files, LibreOffice headless for office→PDF conversion, Microsoft Graph for email. Deployed as one Railway service + Postgres + volume + daily cron.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, pypdf + reportlab, MSAL, httpx, pytest; Vue 3 (Composition API) + Vuetify 3 + Pinia + Vite + TypeScript, pdf.js, signature_pad; Docker multi-stage; GitHub Actions CI.

**Spec:** `docs/superpowers/specs/2026-07-30-internal-esign-design.md` — read it first; it is the authority on behavior.

## Global Constraints

- Python line length 121, ruff rules per Pumasi convention (A, B, COM, D202, E, F, I, N, PERF, RET, SIM, UP, W).
- Vue: Composition API only, `<script setup lang="ts">`.
- All timestamps stored UTC (`TIMESTAMPTZ`), rendered local in UI.
- Field coordinates are normalized 0–1 floats relative to PDF page width/height, origin top-left.
- File keys in DB are relative paths under `DATA_DIR` (default `/data`); all file IO goes through `FileStorage` — never `open()` a data path directly outside `storage.py`.
- Env vars: `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MAIL_SENDER`, `SESSION_SECRET`, `ADMIN_EMAILS` (comma-separated), `JOB_TOKEN`, `DATABASE_URL`, `DATA_DIR`, `APP_BASE_URL`, `DEV_AUTH_BYPASS` (never in prod).
- Upload limit 25 MB; allowed types: pdf, docx, xlsx (extension + magic bytes).
- Audit events are append-only: no update or delete endpoint/code path may touch `audit_events` rows.
- Max 3 reminders per submitter, minimum 3 days between touches.
- Backend tests run with SQLite in-memory is NOT allowed (JSONB, TIMESTAMPTZ); use Postgres via `TEST_DATABASE_URL` (docker `postgres:16` locally / service container in CI).

## Repository Layout

```
pumasi-sign/
├── backend/
│   ├── app/
│   │   ├── main.py            # app factory, router mounting, SPA static serving
│   │   ├── config.py          # pydantic-settings Settings
│   │   ├── db.py              # engine, SessionLocal, Base, get_db dep
│   │   ├── models.py          # User, Template, Submission, Submitter, Signature, AuditEvent
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── auth.py            # Entra OAuth, session cookie, current_user/require_admin deps
│   │   ├── storage.py         # FileStorage protocol, LocalVolumeStorage
│   │   ├── conversion.py      # office→PDF via LibreOffice, page counting
│   │   ├── stamping.py        # signed-PDF generation + audit page
│   │   ├── mailer.py          # Graph sendMail with retry
│   │   ├── audit.py           # record(event, ...) helper
│   │   ├── completion.py      # completion pipeline (stamp → store → email)
│   │   └── routers/
│   │       ├── auth.py        # /api/auth/login|callback|logout|me, dev bypass
│   │       ├── templates.py   # /api/templates CRUD + upload
│   │       ├── submissions.py # /api/submissions create/list/cancel/remind/retry-completion
│   │       ├── signing.py     # /api/sign/{submitter_id} get/open/complete
│   │       ├── users.py       # /api/users list, admin toggle
│   │       ├── files.py       # /api/files/{kind}/... authorized file serving
│   │       └── jobs.py        # /api/jobs/daily (JOB_TOKEN guarded)
│   ├── migrations/            # alembic (env.py imports app.models)
│   ├── tests/
│   │   ├── conftest.py        # app+db fixtures, auth helpers, tmp storage
│   │   ├── fixtures/          # sample.pdf, sample.docx, sample.xlsx
│   │   ├── test_storage.py
│   │   ├── test_conversion.py
│   │   ├── test_auth.py
│   │   ├── test_templates.py
│   │   ├── test_submissions.py
│   │   ├── test_signing.py
│   │   ├── test_stamping.py
│   │   ├── test_mailer.py
│   │   └── test_jobs.py
│   ├── requirements.txt
│   ├── alembic.ini
│   └── pyproject.toml         # ruff config
├── frontend/
│   ├── src/
│   │   ├── main.ts, App.vue
│   │   ├── router/index.ts
│   │   ├── store/auth.ts      # Pinia: me, isAdmin
│   │   ├── utils/http.ts      # axios instance, 401 → login redirect
│   │   ├── views/
│   │   │   ├── DashboardView.vue
│   │   │   ├── TemplateBuilderView.vue
│   │   │   ├── SendView.vue
│   │   │   ├── SignView.vue
│   │   │   └── AdminUsersView.vue
│   │   └── components/
│   │       ├── PdfPage.vue        # renders one pdf.js page to canvas, slots overlay
│   │       ├── FieldBox.vue       # draggable/resizable field rectangle
│   │       └── SignaturePad.vue   # draw/type signature, emits PNG data URL
│   ├── package.json, vite.config.ts, tsconfig.json
│   └── e2e/sign-flow.spec.ts  # Playwright
├── Dockerfile
├── railway.json
├── .github/workflows/ci.yaml
├── .gitignore
└── README.md
```

---

### Task 1: Backend scaffold — config, DB, models, migrations, health

**Files:**
- Create: `backend/requirements.txt`, `backend/pyproject.toml`, `backend/app/{__init__,main,config,db,models}.py`, `backend/alembic.ini`, `backend/migrations/*`, `backend/tests/{conftest.py,test_health.py}`, `.gitignore`

**Interfaces:**
- Produces: `Settings` (config.py) with all env vars from Global Constraints, `get_db` dependency, SQLAlchemy models `User, Template, Submission, Submitter, Signature, AuditEvent` exactly per spec data model, `create_app()` in main.py.
- Status enums as `str` columns with `CheckConstraint`, values per spec (`pending|opened|completed` etc.).

**Steps:**

- [ ] **Step 1:** `requirements.txt`: fastapi, uvicorn[standard], sqlalchemy>=2, alembic, psycopg[binary], pydantic-settings, python-multipart, itsdangerous, msal, httpx, pypdf, reportlab, pytest, pytest-asyncio, httpx (test client via `fastapi.testclient`). `pyproject.toml` with ruff config (line 121, rules from Global Constraints).
- [ ] **Step 2:** Write `config.py` (`Settings(BaseSettings)` reading the env vars; `admin_emails_list` property splitting on comma, lowercased). Write `db.py` (engine from `DATABASE_URL`, `SessionLocal`, `Base(DeclarativeBase)`, `get_db` yield dependency).
- [ ] **Step 3:** Write `models.py` — all six tables exactly as in spec §Data model, with `server_default=func.now()` for created_at, JSONB via `sqlalchemy.dialects.postgresql.JSONB`, FKs with `ondelete="CASCADE"` from submitters→submissions, indexes on `submitters.user_id`, `submissions.status`, `audit_events.submission_id`, unique on `users.email`.
- [ ] **Step 4:** Failing test `test_health.py`: `client.get("/api/health")` returns `{"status": "ok"}`; conftest builds app with test Postgres (`TEST_DATABASE_URL`, default `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`), creates/drops all tables per session, truncates per test. Provide a `docker run` line in conftest docstring for the test DB: `docker run -d --name sign-test-pg -e POSTGRES_PASSWORD=postgres -p 5433:5432 postgres:16`.
- [ ] **Step 5:** Implement `main.py` `create_app()` with `/api/health` router inline; run test → PASS.
- [ ] **Step 6:** Alembic init under `backend/migrations`, `env.py` imports `app.models` and uses `Settings().database_url`; autogenerate initial revision; verify `alembic upgrade head` against test DB creates the six tables.
- [ ] **Step 7:** Commit `feat: backend scaffold with models and migrations`.

### Task 2: Storage + conversion

**Files:**
- Create: `backend/app/storage.py`, `backend/app/conversion.py`, `backend/tests/{test_storage,test_conversion}.py`, `backend/tests/fixtures/{sample.pdf,sample.docx,sample.xlsx}` (generate sample.pdf with reportlab in a fixture-making step; create minimal docx/xlsx with python-docx/openpyxl added as dev deps or check in tiny files).

**Interfaces:**
- Produces:
  - `FileStorage` protocol: `save(key: str, data: bytes) -> None`, `open(key: str) -> bytes`, `exists(key: str) -> bool`, `delete(key: str) -> None`; `LocalVolumeStorage(root: Path)`; `get_storage(settings) -> FileStorage`.
  - `conversion.to_pdf(data: bytes, filename: str, storage: FileStorage, key_prefix: str) -> tuple[str, int]` returning `(pdf_key, page_count)`; raises `ConversionError(reason)` on corrupt/encrypted/unsupported input. PDFs are validated with pypdf (raises on encrypted) and passed through.
  - `conversion.ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx"}` and `sniff_ok(data, ext) -> bool` (magic bytes: `%PDF` for pdf, `PK\x03\x04` for docx/xlsx).
- LibreOffice invocation: `soffice --headless --convert-to pdf --outdir <tmp> <infile>` via subprocess, 120 s timeout. If `soffice` is missing locally, conversion tests for docx/xlsx are skipped with `pytest.mark.skipif(shutil.which("soffice") is None, ...)` — they run in CI/Docker.

**Steps:**

- [ ] **Step 1:** Failing tests: `LocalVolumeStorage` save/open/exists/delete roundtrip in `tmp_path`; path traversal rejected (`key` containing `..` raises `ValueError`).
- [ ] **Step 2:** Implement storage; tests pass.
- [ ] **Step 3:** Failing tests: pdf passthrough returns page_count via pypdf; encrypted pdf raises `ConversionError`; bad magic bytes raises; docx/xlsx converts (skipif no soffice).
- [ ] **Step 4:** Implement conversion; tests pass. Commit `feat: file storage and document conversion`.

### Task 3: Auth — Entra OAuth, sessions, dev bypass

**Files:**
- Create: `backend/app/auth.py`, `backend/app/routers/auth.py`, `backend/tests/test_auth.py`
- Modify: `backend/app/main.py` (mount router, add `SessionMiddleware`-style signed cookie via itsdangerous)

**Interfaces:**
- Produces:
  - Deps: `current_user(request, db) -> User` (401 if no session), `require_admin(user) -> User` (403 if not admin).
  - Session: signed cookie `sign_session` holding `{"uid": user_id}`, itsdangerous `URLSafeTimedSerializer(SESSION_SECRET)`, max age 12 h, HttpOnly, Secure (when APP_BASE_URL is https), SameSite=Lax.
  - Routes: `GET /api/auth/login?next=` → MSAL auth-code redirect to Entra (`scopes=["User.Read"]` delegated—used only for identity; tenant-restricted authority). `GET /api/auth/callback` → exchanges code, validates `tid == MS_TENANT_ID`, upserts user by email (lowercase; name + `entra_oid` from claims; `is_admin = email in ADMIN_EMAILS` on create, and re-asserted True on every login if listed), sets cookie, redirects to `next` (must be a relative path). `POST /api/auth/logout`. `GET /api/auth/me` → `{id, email, name, is_admin}`.
  - Dev bypass: when `DEV_AUTH_BYPASS=1`, `POST /api/auth/dev-login {email, name}` creates/gets user and sets cookie. Guard: raise 404 unless the flag is set. Used by tests and Playwright.
- Consumes: `get_db`, `Settings`, models from Task 1.

**Steps:**

- [ ] **Step 1:** Failing tests: dev-login sets cookie and `/api/auth/me` returns the user; admin email from `ADMIN_EMAILS` gets `is_admin=true`; `/api/auth/me` without cookie → 401; dev-login when flag unset → 404; `next` absolute URL (`https://evil.com`) rejected at login route → 400.
- [ ] **Step 2:** Implement auth.py + router (MSAL `ConfidentialClientApplication`, `initiate_auth_code_flow`/`acquire_token_by_auth_code_flow`, flow dict stashed in short-lived signed cookie). Tests pass.
- [ ] **Step 3:** Commit `feat: Entra ID auth with sessions and dev bypass`.

### Task 4: Templates API + authorized file serving

**Files:**
- Create: `backend/app/routers/templates.py`, `backend/app/routers/files.py`, `backend/app/schemas.py`, `backend/tests/test_templates.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces:
  - `POST /api/templates` (admin, multipart `file`, form `name`) → converts, stores original at `templates/{id}/original.{ext}` and pdf at `templates/{id}/document.pdf`, creates row, returns `TemplateOut {id, name, page_count, fields, created_at}`. 413 over 25 MB; 422 on ConversionError with `{"detail": reason}`.
  - `PUT /api/templates/{id}/fields` (admin, body `{fields: [FieldDef]}`) — `FieldDef {id: str, type: Literal[signature,name,date,text,checkbox], role: str, page: int, x,y,w,h: float (0..1), required: bool}`; validates 0≤x,y and x+w≤1, y+h≤1, page < page_count, roles non-empty strings. Replaces fields wholesale.
  - `GET /api/templates` (admin, excludes `is_adhoc` and archived), `GET /api/templates/{id}`, `POST /api/templates/{id}/archive`.
  - `GET /api/files/template-pdf/{template_id}` → PDF bytes; allowed for admins, and for any submitter of a submission using that template. `GET /api/files/signed-pdf/{submission_id}` → allowed for sender + submitters. `GET /api/files/signature/{signature_id}` → owner or admin only. All 404 when missing, 403 otherwise.
- Consumes: Tasks 1–3 interfaces.

**Steps:**

- [ ] **Step 1:** Failing tests: non-admin create → 403; pdf upload creates template with page_count; bad file → 422; fields PUT validates coords (x+w>1 → 422) and persists; template-pdf served to admin, 403 to plain user; archive hides from list.
- [ ] **Step 2:** Implement schemas + routers; register static-before-dynamic route order. Tests pass.
- [ ] **Step 3:** Commit `feat: templates API with upload, fields, file serving`.

### Task 5: Submissions API + audit log

**Files:**
- Create: `backend/app/routers/submissions.py`, `backend/app/audit.py`, `backend/tests/test_submissions.py`
- Modify: `backend/app/schemas.py`, `backend/app/main.py`

**Interfaces:**
- Produces:
  - `audit.record(db, submission_id, event, actor_user_id=None, ip=None, **detail)` — inserts AuditEvent; never updates.
  - `POST /api/submissions` (admin) body `{template_id, title, message?, signers: [{role, user_id}]}` — validates every template role is mapped exactly once and users exist; creates submission (`pending`) + submitters (`pending`); records `created` + `sent` events; calls `mailer.send_sign_request` per submitter (Task 7 provides it; until then call through a `notify` module-level hook set to no-op — define `notifications.on_submission_created(db, submission)` in this task as a stub that Task 7 fills).
  - Ad-hoc: `POST /api/submissions/adhoc` (admin, multipart file + form `title` + JSON `signers`/`fields` strings) — creates `is_adhoc` template then same path.
  - `GET /api/submissions?mine=sign|sent` — `mine=sign`: submissions where current user is a non-completed submitter; `sent` (admin): created_by me, with per-submitter status. `GET /api/submissions/{id}` for sender/submitters.
  - `POST /api/submissions/{id}/cancel` (sender or admin; only while `pending`) → status cancelled + event.
  - `POST /api/submissions/{id}/remind` (sender; manual reminder respecting reminder cap) → calls `notifications.send_reminders_for(db, submission)`.
  - `SubmissionOut` includes `submitters: [{id, user: {name,email}, role, status, signed_at}]`.
- Consumes: Tasks 1–4.

**Steps:**

- [ ] **Step 1:** Failing tests: create with unmapped role → 422; duplicate role mapping → 422; create writes submitters + audit events (`created`, `sent`); mine=sign lists for signer, not for others; cancel flips status and blocks signing (asserted in Task 6 too); cancel on completed → 409.
- [ ] **Step 2:** Implement; tests pass. Commit `feat: submissions API with audit log`.

### Task 6: Signing API

**Files:**
- Create: `backend/app/routers/signing.py`, `backend/tests/test_signing.py`
- Modify: `backend/app/schemas.py`, `backend/app/main.py`

**Interfaces:**
- Produces:
  - `GET /api/sign/{submitter_id}` (current user must be the submitter's user) → `{submission: {id,title,message,status}, template: {id, page_count, fields}, my_fields: [field ids for my role], my_status, saved_signature_id?}`. First GET when status `pending` flips to `opened` + audit `opened` with IP (`request.client.host`, honoring `X-Forwarded-For` first value — Railway sits behind a proxy; set `root_path`/proxy headers accordingly in uvicorn flags).
  - `POST /api/sign/{submitter_id}/signature` body `{image: dataURL png}` → decodes base64 (max 1 MB), stores at `signatures/{user_id}/{uuid}.png`, upserts `signatures` row, returns `{signature_id}`.
  - `POST /api/sign/{submitter_id}/complete` body `{values: {field_id: value}}` — validates: all required fields for my role present; signature fields reference a signature_id owned by me; date fields ISO date; checkbox bool; text str ≤ 500 chars. Sets values, status `completed`, `signed_at=now`, ip; audit `signed`. If all submitters completed → call `completion.finalize(db, submission_id)` (stub in this task: `completion.py` with `finalize()` that only flips submission status + `completed_at` + audit `completed`; Task 7 extends with stamping, Task 8 with email). Idempotent: complete on already-completed submitter → 200 `{already: true}`; on cancelled submission → 409.
- Consumes: Tasks 1–5.

**Steps:**

- [ ] **Step 1:** Failing tests: other user's link → 403; GET flips pending→opened once; complete with missing required field → 422; signature ownership enforced; last-signer completion flips submission to completed and writes audit; double complete idempotent; cancelled → 409.
- [ ] **Step 2:** Implement; tests pass. Commit `feat: signing API with completion trigger`.

### Task 7: Stamping + completion pipeline

**Files:**
- Create: `backend/app/stamping.py`, `backend/tests/test_stamping.py`
- Modify: `backend/app/completion.py`

**Interfaces:**
- Produces:
  - `stamping.build_signed_pdf(template_pdf: bytes, fields: list[dict], submitters: list[Submitter], users_by_id, signature_images: dict[str, bytes], audit_rows: list[dict]) -> bytes`:
    - For each completed submitter and each field of their role: overlay via reportlab canvas sized to the actual page (`page.mediabox`), converting normalized top-left coords: `pdf_x = x * page_w`, `pdf_y = page_h - (y + h) * page_h`. signature → draw PNG image fitted in box preserving aspect; name → user name text; date → `signed_at` date `YYYY-MM-DD`; text → value; checkbox → "X" when true. Merge overlay onto page with pypdf.
    - Append audit page: title "Signature Certificate", submission title + id, then one block per signer: name, email, role, signed timestamp (UTC ISO), IP. Footer: "Generated by Pumasi Sign".
  - `completion.finalize(db, submission_id, storage, settings)` full version: build signed pdf → `storage.save(f"submissions/{id}/signed.pdf")` → set `signed_pdf_key`, status completed, completed_at → audit `completed` → `notifications.on_submission_completed(db, submission)` (still no-op until Task 8). Stamping failure: log exception, leave submission pending, re-raise nothing (signing response still succeeds); expose `POST /api/submissions/{id}/retry-completion` (sender/admin) that re-runs finalize when all submitters are completed and no signed pdf exists yet — add this route in `routers/submissions.py` here.
- Consumes: storage, models, signing flow.

**Steps:**

- [ ] **Step 1:** Failing tests: build a 1-page PDF fixture with known size; place a text field at (0.5, 0.5, 0.2, 0.05); assert output PDF page count = input + 1 (audit page) and extracted text (pypdf `extract_text`) contains the value, signer name on audit page; signature PNG placement doesn't raise and output opens with pypdf.
- [ ] **Step 2:** Implement stamping; tests pass.
- [ ] **Step 3:** Failing test: full-flow — create template + submission via API, both signers complete → submission completed, `signed_pdf_key` set, `/api/files/signed-pdf/{id}` serves bytes starting `%PDF`; simulated stamping failure (monkeypatch build_signed_pdf to raise) leaves submission pending, then retry-completion succeeds.
- [ ] **Step 4:** Implement full finalize + retry route; tests pass. Commit `feat: PDF stamping and completion pipeline`.

### Task 8: Mailer + notifications + daily job

**Files:**
- Create: `backend/app/mailer.py`, `backend/app/notifications.py` (replace stub), `backend/app/routers/jobs.py`, `backend/tests/{test_mailer,test_jobs}.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces:
  - `mailer.send(to: list[str], subject: str, html: str, attachments: list[tuple[filename, bytes]] = []) -> bool` — Graph `POST /v1.0/users/{MAIL_SENDER}/sendMail` with client-credentials token (msal `ConfidentialClientApplication.acquire_token_for_client`, cached); retries 3× with backoff 1/4/16 s on 5xx/429/network; returns False after final failure (never raises to callers).
  - `notifications.on_submission_created(db, submission)` — per submitter: email "{sender} requests your signature: {title}" with link `{APP_BASE_URL}/sign/{submitter_id}`; sets `submitter.email_status` to `sent`/`failed`.
  - `notifications.on_submission_completed(db, submission)` — to all submitters + sender, signed PDF attached (fetch via storage).
  - `notifications.send_reminders_for(db, submission)` and `notifications.run_daily_reminders(db)` — selects submitters `status in (pending, opened)` on pending submissions where `now - max(created_at, last_reminded_at) >= 3 days` and `reminder_count < 3`; sends reminder, increments count, sets `last_reminded_at`, audit `reminded`.
  - `POST /api/jobs/daily` header `X-Job-Token: {JOB_TOKEN}` (403 otherwise) → runs reminders + writes backup: `pg_dump -Fc` to `backups/db-YYYYMMDD.dump` (subprocess, using DATABASE_URL) and tar of data dirs excluding `backups/` to `backups/files-YYYYMMDD.tar`; keeps last 14 of each; returns counts. If `pg_dump` binary missing, skip DB dump with warning log (documented limitation; Dockerfile installs postgresql-client).
- Consumes: storage, models, submissions/completion hooks from Tasks 5–7 (fill the stubs).

**Steps:**

- [ ] **Step 1:** Failing tests with Graph mocked via `httpx.MockTransport`-style injection (mailer accepts optional `transport` for tests): success path builds correct JSON (recipients, attachment base64); 500 retries then False. Reminder query test: submitter created 4 days ago → selected; reminded yesterday → not; reminder_count=3 → not; cancelled submission → not.
- [ ] **Step 2:** Implement mailer + notifications; wire `on_submission_created` into submissions router and `on_submission_completed` into completion. Tests pass.
- [ ] **Step 3:** Failing test: `/api/jobs/daily` wrong token → 403; with token → 200 and reminder side effects (mail mocked).
- [ ] **Step 4:** Implement jobs router; tests pass. Commit `feat: email notifications, reminders, daily job`.

### Task 9: Frontend scaffold + dashboard

**Files:**
- Create: `frontend/` via `npm create vite@latest frontend -- --template vue-ts`; add vuetify, pinia, vue-router, axios, pdfjs-dist, signature_pad; `src/{main.ts,App.vue,router/index.ts,store/auth.ts,utils/http.ts,views/DashboardView.vue}`
- Modify: `backend/app/main.py` — serve `frontend/dist` at `/` with SPA fallback (any non-`/api` 404 → `index.html`).

**Interfaces:**
- Produces: `http` axios instance (baseURL `/api`, on 401 redirect `window.location = "/api/auth/login?next=" + encodeURIComponent(location.pathname)`); auth store `useAuthStore` with `me`, `isAdmin`, `fetchMe()`; router routes `/` (dashboard), `/templates/:id/build`, `/send/:templateId?`, `/sign/:submitterId`, `/admin/users`; nav guard calls `fetchMe()` once.
- Dashboard: "Waiting for my signature" list (GET `/api/submissions?mine=sign` → rows link to `/sign/{my submitter id}` — include `my_submitter_id` in that response, add to Task 5 schema); admins additionally see "Sent" table (title, created, per-signer status chips, cancel + remind buttons) and "Templates" table (name, pages, Send + Build + Archive buttons, "New template" upload dialog posting multipart to `/api/templates` then routing to builder).
- Vite dev proxy `/api` → `http://localhost:8000`.

**Steps:**

- [ ] **Step 1:** Scaffold, wire Vuetify + router + store; `npm run build` succeeds; backend serves built SPA (manual check: `/` returns index.html, `/api/health` still JSON).
- [ ] **Step 2:** Implement dashboard views against the API; add `my_submitter_id` to submissions list schema in backend with test.
- [ ] **Step 3:** Commit `feat: frontend scaffold and dashboard`.

### Task 10: Template builder UI

**Files:**
- Create: `frontend/src/views/TemplateBuilderView.vue`, `frontend/src/components/{PdfPage.vue,FieldBox.vue}`

**Interfaces:**
- `PdfPage.vue` props `{src: string (blob url), page: number}`; renders with pdfjs-dist (`getDocument`, canvas at scale fitting container width, devicePixelRatio-aware); emits `rendered(widthPx, heightPx)`; default slot positioned absolute over the canvas.
- `FieldBox.vue` props `{field: FieldDef, pageWidth, pageHeight, color}`; renders at `left = field.x * pageWidth` etc.; drag (pointer events) and resize (bottom-right handle) update normalized coords, clamped to page; delete button; label shows `${field.role}: ${field.type}`.
- Builder view: loads template + pdf (`/api/files/template-pdf/{id}` as blob), role manager (add/rename roles, each role a color from a fixed 6-color palette), palette of field type buttons — click then click-drag on a page to place with sensible default size (signature 0.2×0.06, text 0.2×0.04, date 0.12×0.04, name 0.15×0.04, checkbox 0.03 square); required toggle per field; Save → PUT fields; "Send" button → `/send/{templateId}`.

**Steps:**

- [ ] **Step 1:** Implement components + view; verify in dev against a real uploaded PDF: place fields on page 2 of a multi-page doc, save, reload → positions identical.
- [ ] **Step 2:** Commit `feat: template builder with drag-and-drop fields`.

### Task 11: Send flow + signing UI + admin users

**Files:**
- Create: `frontend/src/views/{SendView.vue,SignView.vue,AdminUsersView.vue}`, `frontend/src/components/SignaturePad.vue`

**Interfaces:**
- SendView: template picker (if no route param); title (default template name) + message; one user-autocomplete per role (GET `/api/users`); submit → POST `/api/submissions` → snackbar + back to dashboard.
- SignaturePad: dialog with tabs Draw (signature_pad on canvas, clear button) / Type (text input rendered in cursive font to canvas); emits `save(dataUrl)`.
- SignView: loads `/api/sign/{submitterId}`; renders all pages via PdfPage; my fields overlaid as interactive inputs (others' fields shown greyed at 40% opacity); signature field click → SignaturePad (pre-filled from `saved_signature_id` if present — show stored image with "use saved" / "redraw"); date fields default today; validate required before enabling "Finish"; POST signature then complete; success screen; `already`/409 → friendly "already handled / no longer active" state.
- AdminUsersView: table of users, `is_admin` switch → `PUT /api/users/{id}` (add endpoint to `routers/users.py` with test if not present: admin-only, cannot remove own admin flag — 409).
- Consumes: components/HTTP from Tasks 9–10; APIs from Tasks 4–6.

**Steps:**

- [ ] **Step 1:** Add/verify `PUT /api/users/{id}` backend endpoint + tests (admin gate, self-demotion 409).
- [ ] **Step 2:** Implement the three views + SignaturePad; manual dev-flow check with dev bypass: send to two users, sign as both, download signed PDF.
- [ ] **Step 3:** Commit `feat: send flow, signing view, admin users`.

### Task 12: Docker, CI, Railway deploy

**Files:**
- Create: `Dockerfile`, `railway.json`, `.github/workflows/ci.yaml`, `README.md`
- Modify: none

**Interfaces:**
- Dockerfile multi-stage: stage 1 `node:22-slim` builds frontend; stage 2 `python:3.12-slim-bookworm` + `apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc postgresql-client fonts-dejavu` + backend deps + copied `frontend/dist`; CMD runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`.
- `railway.json`: build via Dockerfile; healthcheck `/api/health`.
- CI: services postgres:16; ruff check + format --check; pytest (soffice present via `apt-get install libreoffice-writer libreoffice-calc` — or run tests in the built Docker image); frontend `npm ci && npm run build` + `vue-tsc --noEmit`.
- Deploy (execute, not just write): `gh repo create pumasi-ai/pumasi-sign --private --source . --push` (or under user account if org create fails); `railway init`/`railway add` Postgres, volume mount `/data`, set env vars (generate `SESSION_SECRET`/`JOB_TOKEN` with `openssl rand -hex 32`; `ADMIN_EMAILS=admin@pumasi.ai,admin@pumasi.ai`; MS creds from the email .env; `MAIL_SENDER=admin@pumasi.ai`; `DEV_AUTH_BYPASS` unset); `railway up`; set `APP_BASE_URL` to the generated domain; configure Railway cron hitting `/api/jobs/daily` daily 09:00 UTC (Railway cron service or scheduled job calling curl with the token).
- README: purpose, local dev (test DB docker line, backend uvicorn, frontend vite), env var table, deploy notes, **the manual Entra step**: add Web redirect URI `https://<domain>/api/auth/callback` to app registration `5434f64e-4034-46bc-9447-1a4fc442616c`.

**Steps:**

- [ ] **Step 1:** Write Dockerfile + build locally (`docker build .`) → image builds, container serves `/api/health` and SPA.
- [ ] **Step 2:** CI workflow; push; verify green.
- [ ] **Step 3:** Create GitHub repo, push. Railway project, Postgres, volume, env vars, deploy, cron. Verify deployed `/api/health` and SPA load. Commit `chore: docker, CI, railway deploy`.

### Task 13: Playwright e2e

**Files:**
- Create: `frontend/e2e/sign-flow.spec.ts`, `frontend/playwright.config.ts`

**Interfaces:**
- Runs against local stack (backend `DEV_AUTH_BYPASS=1` + built frontend, test Postgres). Flow: dev-login as admin → upload fixture PDF as template → builder: place signature+date for role "Employee", signature for role "Manager" → send to two dev users → dev-login as each, sign (draw on pad) → dashboard shows completed → download signed PDF, assert content-type and size > original.

**Steps:**

- [ ] **Step 1:** Config + spec; run headed locally until green; wire into CI as a separate job (build image, run container, run Playwright).
- [ ] **Step 2:** Commit `test: e2e sign flow`.

---

## Self-Review Notes

- Spec coverage: auth ✔ (T3), templates/conversion ✔ (T2/T4), send+audit ✔ (T5), sign ✔ (T6), stamping+audit page ✔ (T7), email+reminders+backup ✔ (T8), UI ✔ (T9–11), deploy+cron+manual Entra step ✔ (T12), e2e ✔ (T13). Ad-hoc send: backend T5, UI reachable via "New template" + immediate send (acceptable v1).
- Type consistency: `FieldDef` defined once (T4) and reused by T7/T10/T11; `my_submitter_id` added in T9 back into T5's schema — noted in both.
- No placeholder steps remain; conversion/e2e steps that need LibreOffice/Docker are explicitly marked for CI.
