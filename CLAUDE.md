# CLAUDE.md

Pumasi Sign — internal e-signature service for Pumasi employees; external
recipients can sign via emailed token links and email verification codes but
cannot log in or send. Vue 3/Vuetify SPA, served with the API by a Cloudflare
Worker.

## Read this before you touch anything: there are two backends

This repository carries **two complete, independent backends for one product**.

| Tree | What it is | Does it serve users? |
| :--- | :--- | :--- |
| **`service/`** | Cloudflare Worker — Durable Object (SQLite) store, R2 documents, `frontend/dist` as its static assets | **Yes.** `service/wrangler.jsonc` claims **`sign.pumasi.ai`** as a `custom_domain`, and that host answers with the worker's error bodies. |
| **`backend/`** | FastAPI + Postgres + Alembic, built by `Dockerfile`, deployable to Railway | **No.** It is what CI's `backend` and `e2e` jobs cover, and what `docs/superpowers/specs/2026-07-30-internal-esign-design.md` designs. Nothing in production reaches it. |

**Which of the two *is* Pumasi Sign is an open question — `pumasi/DECISIONS.md`
Q-018 — and it is the steward's, not an agent's.** Do not delete either tree,
re-point the domain, or migrate data on your own authority. Until Q-018 is
answered:

- **A green `backend` or `e2e` job is not evidence about production.** Those
  jobs test a tree no user reaches. That is Q-018's default part (c), and it
  is why `service/` now has a CI job of its own.
- The two trees **disagree about who may hold an account**: `backend/` gates
  on `ALLOWED_EMAIL_DOMAINS` (default `pumasi.ai`), the worker's
  `establishSession` (`service/src/durable.ts`) creates an account for any
  verified email. Fix a bug in the tree you are actually asked about.

Setup for a new machine, env vars and deployment steps: `README.md`.

## Commands

Worker — the deployed tree (from `service/`):

```bash
npm ci                  # deps
npm run build           # tsc -p tsconfig.json → service/dist; also the only type-check
npm test                # node --test dist/test/*.test.js — RUNS dist/, so build first
npm run dev             # wrangler dev
```

**`npm test` here runs the *compiled* tree and `service/dist/` is
`.gitignore`d.** Without `npm run build` first it matches no files, runs zero
assertions and exits 0. CI guards that with
`.github/scripts/assert-service-suite-ran.sh`; do the same locally, and see
`spec/0002/SPEC.md`.

Frontend (from `frontend/`):

```bash
npx vue-tsc -b --force  # type-check — the -b is required, see below
npm run test:unit       # vitest
npm run build           # emits frontend/dist, served by the worker's ASSETS binding
npx playwright test     # e2e against backend/ (needs the app running; see the ci.yaml e2e job)
```

**`vue-tsc` without `-b` checks nothing.** `frontend/tsconfig.json` is a
solution file — empty `files`, two `references` — so `--noEmit` alone has no
program and exits 0 on a tree with type errors. Measured, not assumed.

Backend — the second implementation (from `backend/`, venv at `backend/.venv`):

```bash
ruff check . && ruff format --check .   # lint
pytest                                  # needs local Postgres on :5433, see README
```

## Key facts

### `service/` — the deployed worker

- Layout: `src/worker.ts` (entrypoint, routing), `src/durable.ts` (the Durable
  Object: sessions, envelopes, signing, the API surface), `src/core/stamping.ts`
  (PDF field stamping + audit certificate), `src/storage/r2.ts`,
  `src/convert/graph.ts` (Office → PDF via Microsoft Graph), `src/mail.ts`,
  `src/feedback.ts` (in-app feedback → GitHub issues).
- **Test coverage here is uneven, and the shape of the unevenness is the thing
  to know before you trust a green count.** `src/test/` holds **eight**
  `*.test.ts` files. **Six** of them construct the real Durable Object through
  `src/test/support/durable-harness.ts` — whole schema, migrations, routing —
  and drive it through its own `fetch()`: sessions and `establishSession`, the
  OAuth callback, envelope state transitions, correction, expiry (including
  `worker.ts`'s `scheduled()`), and `finalize`'s stamping branch end to end
  including `storage/r2.ts` against an in-memory bucket. The other **two**
  (`stamping.test.ts`, `stamping-multi-signer.test.ts`) call
  `core/stamping.ts` directly and assert only the *shape* of what it returns.
  **Still covered by nothing: `mail.ts` beyond its unconfigured throw,
  `feedback.ts`, and `convert/graph.ts`** — all three cross a network boundary
  this suite has no stubs for. Widening that is `roadmap/BACKLOG.md`'s owner's
  call, not a side errand.
- Bindings and vars live in `service/wrangler.jsonc`; secrets are set with
  `wrangler secret put`, never committed.

### `backend/` — the FastAPI implementation

- **Tests are Postgres-only** (JSONB/TIMESTAMPTZ) — never SQLite. Test DB URL
  comes from `TEST_DATABASE_URL`, default
  `postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`.
- Office-document conversion tests auto-skip when LibreOffice (`soffice`)
  isn't on `PATH` (image conversion is in-process and always tested).
- Migrations are Alembic and run automatically on container start (Docker
  `CMD` does `alembic upgrade head` before uvicorn).
- Local login uses `DEV_AUTH_BYPASS=1` (`/api/auth/dev-login`); Entra ID SSO or
  passwordless email magic links otherwise (`/login`, domains gated by
  `ALLOWED_EMAIL_DOMAINS`, default `pumasi.ai`). `DEV_AUTH_BYPASS` must never
  be set anywhere reachable.
- Layout: `backend/app/routers/` (auth, templates, submissions, signing, files,
  users, jobs), plus `models.py`, `storage.py` (files under `DATA_DIR`),
  `stamping.py` (PDF field stamping/watermark), `conversion.py` (LibreOffice),
  `graph.py` (shared Microsoft Graph auth), `mailer.py`/`notifications.py`
  (Microsoft Graph mail), `sharepoint.py` (SharePoint archive mirror),
  `audit.py`.

### Domain model (both trees)

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

## CI

`.github/workflows/ci.yaml`, four jobs, on every push and pull request:
`backend` (ruff + pytest against Postgres), `frontend` (type-check, vitest,
build), `service` (npm ci → build → suite → the ran-nothing guard), and `e2e`
(Playwright against a Docker image of `backend/`).

`pumasi/tools/gate.sh` is the merge gate; its step 1 runs `npm test` at this
repository's root, which runs the frontend unit suite and type-check only.
**It does not run the `service` suite** — closing that is a reported gap, not
a done thing.

## Deployment

**What serves `sign.pumasi.ai` is the worker, and it is deployed with
`wrangler deploy` from `service/`.**

- **Who may deploy a merged build is `pumasi/DECISIONS.md` Q-012, which is
  open and explicitly outside CHARTER Part 0's proceed-on-default rule.** Do
  not deploy because a job finished; check that entry first.
- `frontend/dist` must be built before deploying: `wrangler.jsonc` serves it
  through the `ASSETS` binding, so a stale `dist` ships a stale SPA.

The Railway stack below belongs to `backend/`. **It does not serve users**,
and a run that follows it and reports "shipped" has deployed a tree nobody
reaches — that sentence is Q-018's, written from an incident.

- Railway project `pumasi-sign` (env `production`): main service `pumasi-sign`
  (Dockerfile build, healthcheck `/api/health`, volume at `/data`), Railway
  Postgres, and cron service `pumasi-sign-cron` (daily `POST /api/jobs/daily`
  at 09:00 UTC).
- `railway up` only for one-off manual deploys. The cron service must be
  deployed with
  `railway up deploy/cron --path-as-root --service pumasi-sign-cron --detach`
  — both flags are mandatory (`deploy/cron/README.md` explains why).
- Secrets (`SESSION_SECRET`, `JOB_TOKEN`, Entra credentials) live only in
  Railway env vars — never commit them. `railway variables` to view.
