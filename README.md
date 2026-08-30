# Pumasi Sign

A minimal internal e-signature service for Pumasi employees; external recipients can sign via emailed token links and email verification codes but cannot log in or send. One FastAPI service, one Postgres database, one Railway volume.

See `docs/superpowers/specs/2026-07-30-internal-esign-design.md` for the full
design doc.

## Stack

- Backend: FastAPI (Python 3.12) + SQLAlchemy + Alembic + PostgreSQL
- Frontend: Vue 3 + Vuetify + Vite, built to static assets and served by the
  backend (`frontend/dist`, mounted by `backend/app/main.py`)
- Auth: Microsoft Entra ID SSO (MSAL), session cookie
- Document conversion: LibreOffice headless (Office, OpenDocument, rtf/txt →
  PDF); images (png/jpg/gif/webp/bmp/tiff) convert in-process via
  Pillow/reportlab
- Hosting: Railway (single Docker service + Postgres + volume + daily cron)

## Setting up on a new machine

Everything needed to work on this project from a fresh computer. No secrets
live in the repo — production values are in Railway (`railway variables`).

1. Install the prerequisites:
   - **Git** and the **GitHub CLI** (`gh`) — repo lives at
     `https://github.com/pumasi-ai/pumasi-sign`
   - **Python 3.12**
   - **Node 22**
   - **Docker Desktop** (local test Postgres + building the prod image)
   - **Railway CLI** (`npm i -g @railway/cli`)
   - Optional: **LibreOffice** (`soffice` on `PATH`) to run the office-document
     conversion tests locally; they auto-skip without it.
2. Clone and set up both halves:

   ```bash
   gh auth login          # or plain git clone with HTTPS
   git clone https://github.com/pumasi-ai/pumasi-sign.git
   cd pumasi-sign
   cd backend && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt
   cd ../frontend && npm install
   ```

3. Create the local env file from the committed template (working dev
   defaults, no secrets — the backend auto-loads `backend/.env`):

   ```bash
   cp backend/.env.example backend/.env
   ```

4. Start the local test database and run the test suite (see
   [Local development](#local-development) below for the exact commands).
5. Link the Railway CLI to the production project:

   ```bash
   railway login
   railway link   # pick project "pumasi-sign", environment "production", service "pumasi-sign"
   ```

   `railway variables` then shows every production env var (including
   `SESSION_SECRET`/`JOB_TOKEN`) if you ever need them. Copy individual
   values into `backend/.env` when a local task needs a real secret (e.g.
   testing Entra SSO or Graph mail) — never commit them; `backend/.env` is
   gitignored, only `backend/.env.example` lives in the repo.

## Local development

### Backend

Requires Python 3.12 and a local Postgres instance for tests (schema uses
Postgres-only features — JSONB, TIMESTAMPTZ — so SQLite is never used).
Start a local test database with:

```bash
docker run -d --name sign-test-pg -e POSTGRES_PASSWORD=postgres -p 5433:5432 postgres:16
docker exec sign-test-pg psql -U postgres -c "CREATE DATABASE pumasi_sign_test"
```

The test database URL is read from `TEST_DATABASE_URL`, defaulting to the
container above (`postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`).

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
ruff check .
ruff format --check .
pytest
```

Office-document conversion tests are skipped automatically when `soffice`
(LibreOffice) isn't on `PATH` — install
`libreoffice-writer`/`libreoffice-calc`/`libreoffice-impress` to run them
locally.

To run the app itself, set up a normal (non-test) Postgres database, create
`backend/.env` from the committed template (its defaults enable dev auth
bypass so you can log in without Entra), apply migrations, and start uvicorn:

```bash
cp .env.example .env   # from backend/; adjust DATABASE_URL if yours differs
alembic upgrade head
uvicorn app.main:app --reload
```

The backend auto-loads `backend/.env` (pydantic-settings), so no `export`s
are needed. Environment variables set in the shell still win over `.env`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

`npm run build` (`vue-tsc -b && vite build`) produces `frontend/dist`, which
the backend serves as the SPA when present (falls back to `index.html` for
any non-`/api` 404 so client-side routes survive a refresh/deep link).

## Environment variables

Local dev values for these live in `backend/.env.example` (committed, no
secrets) — copy it to `backend/.env`, which the backend auto-loads.
Production values live only in Railway (`railway variables`).

| Variable | Purpose |
|---|---|
| `MS_TENANT_ID` | Entra tenant ID; ID tokens are rejected unless their `tid` claim matches this |
| `MS_CLIENT_ID` | Entra app registration client ID (MSAL auth-code flow) |
| `MS_CLIENT_SECRET` | Entra app registration client secret |
| `MAIL_SENDER` | Address mail is sent from via Microsoft Graph (`Mail.Send`, app-only) |
| `SESSION_SECRET` | Signing key for the session and auth-flow cookies (`itsdangerous`) — generate with `openssl rand -hex 32` |
| `ADMIN_EMAILS` | Comma-separated list of emails auto-granted `is_admin` on first login (and promoted, never demoted, on later logins) |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated email domains allowed to use magic-link email login (default `pumasi.ai`) |
| `JOB_TOKEN` | Shared secret required in the `X-Job-Token` header by `POST /api/jobs/daily` — generate with `openssl rand -hex 32` |
| `DATABASE_URL` | SQLAlchemy-style Postgres URL, e.g. `postgresql+psycopg://user:pass@host:port/db` |
| `DATA_DIR` | Root directory for uploaded/generated files and backups (default `/data`; the Railway volume mount point) |
| `APP_BASE_URL` | Public base URL of the deployed app (used for the Entra redirect URI and to decide whether session cookies are marked `secure`) |
| `FEEDBACK_EMAIL` | Recipient for in-app feedback submissions (default `legal@pumasi.ai`) |
| `SP_DRIVE_ID` | Microsoft Graph drive ID for the SharePoint archive site (`b!yfEmPUN-7UyS1Z6xZQVh6YppZfIgzWZBnTKWVL9zhK0zexu6vG5qQ5PA-VUSVyeB`) |
| `SP_ARCHIVE_FOLDER` | SharePoint folder name to mirror signed submissions to (`Signed_document_archive`) — deploy code first, set this var, then run the next daily job to backfill |
| `GRAPH_CONVERT` | If truthy, docx/doc/pptx/ppt uploads convert to PDF via Microsoft Graph (Word/PowerPoint's own rendering; needs `SP_DRIVE_ID` + Graph creds), with LibreOffice as automatic fallback. Spreadsheets (xlsx/xls/ods) always use LibreOffice (one-page-per-sheet export) |
| `DEV_AUTH_BYPASS` | If set truthy, enables `/api/auth/dev-login` for local development. **Must be unset in production.** |
| `PORT` | Listen port for uvicorn (set automatically by Railway; used by the Docker `CMD`) |

## Docker

```bash
docker build -t pumasi-sign .
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e DATABASE_URL="postgresql+psycopg://postgres:postgres@host.docker.internal:5433/pumasi_sign_test" \
  -e SESSION_SECRET="dev-secret" \
  -e DATA_DIR=/data \
  pumasi-sign
```

The image is a two-stage build: `node:22-slim` builds the frontend SPA, then
a `python:3.12-slim-bookworm` runtime installs LibreOffice (Office/OpenDocument/rtf/txt
→ PDF conversion), `postgresql-client` (for the daily job's `pg_dump` backup), and
fonts: `fonts-dejavu` plus `fonts-noto-cjk`/`fonts-noto-core` (LibreOffice
conversion of Korean/Japanese/Chinese and other non-Latin text),
`fonts-nanum` (`app/stamping.py`'s reportlab fallback font — the Noto CJK
TTCs are CFF-outline and reportlab can't embed them, NanumGothic is
TrueType), and `fonts-liberation`/`fonts-crosextra-carlito`/
`fonts-crosextra-caladea` (metric-compatible substitutes for
Arial/Times/Courier, Calibri, and Cambria so converted Office documents
keep their layout instead of reflowing). The container's `CMD` runs `alembic upgrade head` before
starting `uvicorn`, so migrations are applied automatically on every deploy.

## CI

`.github/workflows/ci.yaml` runs on every push/PR:

- **backend** job: spins up a `postgres:16` service container, installs
  LibreOffice, runs `ruff check`, `ruff format --check`, and `pytest`
  (`TEST_DATABASE_URL` pointed at the service container).
- **frontend** job: `npm ci`, `vue-tsc --noEmit`, `npm run build`.

## Deployment (Railway)

Single Railway service built from the repo `Dockerfile` (see `railway.json`
for the build/healthcheck config — healthcheck path `/api/health`), plus a
Railway-managed Postgres database and a volume mounted at `/data`.

### Day-to-day deploys: GitHub auto-deploy (recommended)

Connect the Railway service to the GitHub repo so every push to `main`
deploys automatically — no Railway CLI or local checkout needed:

1. Railway dashboard → `pumasi-sign` service → **Settings → Source →
   Connect Repo** → `pumasi-ai/pumasi-sign`, branch `main`.
2. In the same Source settings, enable **Wait for CI** ("check suites") so
   Railway only deploys after the GitHub Actions checks (lint, pytest,
   type-check, e2e) pass. Without this, Railway deploys the moment you push,
   even if CI later fails.
3. Nothing else to configure: `railway.json` in the repo root is picked up
   automatically (Dockerfile build, `/api/health` healthcheck), migrations
   run on container start, and all env vars stay on the service.

After that the workflow is simply: commit → push to `main` → CI passes →
Railway deploys. `railway up` remains available for one-off deploys of
uncommitted work, but shouldn't be the normal path.

The `pumasi-sign-cron` service (see `deploy/cron/README.md`) almost never
changes; the simplest choice is to leave it CLI-deployed. If you want it on
GitHub too, connect the same repo to that service and set its
**Settings → Source → Root Directory** to `deploy/cron` (the dashboard
equivalent of `railway up --path-as-root`).

### Initial provisioning

Steps (already performed for the current deployment; kept here for anyone
who needs to reproduce or redeploy):

1. `railway init` — create the Railway project.
2. `railway add --database postgres` — provision Postgres; Railway exposes
   its connection string as a reference variable.
3. Attach a volume mounted at `/data` to the service (Railway dashboard or
   `railway volume add --mount-path /data`).
4. `railway variables --set "KEY=VALUE"` for every variable in the table
   above except `PORT` (Railway sets it) and `DEV_AUTH_BYPASS` (left unset).
   `DATABASE_URL` is set to the Postgres service's reference variable
   (`${{Postgres.DATABASE_URL}}`, converted to the `postgresql+psycopg://`
   form the app expects).
5. `railway up` — build and deploy the Docker image.
6. `railway domain` — generate the public domain, then
   `railway variables --set "APP_BASE_URL=https://<generated-domain>"` and
   redeploy so the app knows its own public URL (used for the Entra redirect
   URI and for marking session cookies `secure`).
7. Configure a Railway cron job/service that runs daily at **09:00 UTC** and
   calls:

   ```bash
   curl -X POST "https://<domain>/api/jobs/daily" -H "X-Job-Token: $JOB_TOKEN"
   ```

   This triggers `run_daily_job` (`backend/app/routers/jobs.py`): signature
   reminder emails plus a `pg_dump` + data-directory backup to `/data/backups`
   (pruned to the newest 14 of each). The currently-deployed cron service's
   build context (`Dockerfile` + `railway.json`) is checked into
   `deploy/cron/` — see `deploy/cron/README.md` for how to redeploy it.

`JOB_TOKEN` and `SESSION_SECRET` were generated with `openssl rand -hex 32`
and are set only as Railway environment variables — never committed. Current
values are retrievable by anyone with Railway project access via
`railway variables`.

### Entra app registration (resolved 2026-07-31)

Login and mail both use the **EmailAutomationApp** registration, client ID
`ef91592e-bb34-4e9d-9a07-ae7ef925396d`, in the Pumasi tenant
(`d2c16235-95cb-4ee8-9bd7-4e8db56c9ad4`) — deployed as
`MS_CLIENT_ID`/`MS_CLIENT_SECRET`/`MS_TENANT_ID` on Railway. Configured on
the app registration:

- **Web redirect URI**: `https://sign.pumasi.ai/api/auth/callback`
  (the app moved to the custom domain `sign.pumasi.ai` on 2026-08-01 and
  the original `pumasi-sign-production.up.railway.app` domain was removed;
  if the domain ever changes again, add the new
  `https://<domain>/api/auth/callback` alongside it)
- **API permissions**: `User.Read` (Delegated, for sign-in) and `Mail.Send`
  (Application, for notification emails), with admin consent granted.

Historical note: the original design spec referenced app registration
`5434f64e-4034-46bc-9447-1a4fc442616c`; the decision (2026-07-31) was to
reuse EmailAutomationApp instead, since its credentials were already
provisioned and it already held the Mail.Send grant.
