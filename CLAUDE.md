# CLAUDE.md

Pumasi Sign — internal e-signature service for Pumasi employees; external recipients can sign via emailed token links and email verification codes but cannot log in or send. FastAPI backend + Vue 3/Vuetify SPA served as static assets by the
backend, Postgres, hosted on Railway. Full design doc:
`docs/superpowers/specs/2026-07-30-internal-esign-design.md`. Setup for a new
machine, env vars, and deployment steps: `README.md`.

## Commands

Backend (from `backend/`, venv at `backend/.venv`):

```bash
ruff check . && ruff format --check .   # lint
pytest                                  # needs local Postgres on :5433, see README
```

Frontend (from `frontend/`):

```bash
npx vue-tsc --noEmit    # type-check
npm run build           # emits frontend/dist, served by the backend
npx playwright test     # e2e (needs the app running; see .github/workflows/ci.yaml e2e job)
```

## Key facts

- **Tests are Postgres-only** (JSONB/TIMESTAMPTZ) — never SQLite. Test DB URL
  comes from `TEST_DATABASE_URL`, default
  `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`.
- Office-document conversion tests auto-skip when LibreOffice (`soffice`)
  isn't on `PATH` (image conversion is in-process and always tested).
- Migrations are Alembic and run automatically on container start (Docker
  `CMD` does `alembic upgrade head` before uvicorn).
- Local login uses `DEV_AUTH_BYPASS=1` (`/api/auth/dev-login`); production
  uses Entra ID SSO or passwordless email magic links (`/login`, domains
  gated by `ALLOWED_EMAIL_DOMAINS`, default `pumasi.ai`).
  `DEV_AUTH_BYPASS` must never be set in production.
- Backend layout: `backend/app/routers/` (auth, templates, submissions,
  signing, files, users, jobs), plus `models.py`, `storage.py` (files under
  `DATA_DIR`), `stamping.py` (PDF field stamping/watermark), `conversion.py`
  (LibreOffice), `graph.py` (shared Microsoft Graph auth), `mailer.py`/`notifications.py` (Microsoft Graph mail),
  `sharepoint.py` (SharePoint archive mirror), `audit.py`.
- "Envelope" is the user-facing term for a submission. Submission statuses:
  `draft` (saved unsent, invisible to recipients until `POST /{id}/send`),
  `pending`, `completed`, `cancelled` (UI: "Voided"), `declined`, `expired`
  (past its optional `expires_at` deadline — flipped by the daily job).
- Drafts reopen in the full Send wizard (`/send/draft/:id`, recreate-on-save:
  saving/sending creates a fresh envelope and deletes the superseded draft).
  "Copy" (DocuSign-style, `POST /{id}/copy`) turns any envelope into a
  standalone ad-hoc draft carrying entered text/choice values as prefills;
  templates copy via `POST /api/templates/{id}/copy`.
- Sending and template creation are gated by `users.can_send` (default `true` for
  internal users, admin-revocable; external users can only sign). Pending and draft
  envelopes can be corrected (title/message/signers/document) by their sender or an
  admin. Templates are private per sender unless `shared` (owner-toggled; shared =
  org-wide send-only).

## Deployment

Railway project `pumasi-sign` (env `production`): main service
`pumasi-sign` (Dockerfile build, healthcheck `/api/health`, volume at
`/data`), Railway Postgres, and cron service `pumasi-sign-cron` (daily
`POST /api/jobs/daily` at 09:00 UTC).

- Normal deploys go through GitHub: push to `main` → GitHub Actions CI →
  Railway auto-deploy (see README "Deployment"). `railway up` only for
  one-off manual deploys.
- The cron service must be deployed with
  `railway up deploy/cron --path-as-root --service pumasi-sign-cron --detach`
  — both flags are mandatory (`deploy/cron/README.md` explains why).
- Secrets (`SESSION_SECRET`, `JOB_TOKEN`, Entra credentials) live only in
  Railway env vars — never commit them. `railway variables` to view.
