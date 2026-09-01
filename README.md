# Pumasi Sign

Send a document, drop the fields on it, and get back a signed PDF with a
SHA-256 audit certificate appended to the last page. Senders sign in with
Google or Microsoft. The person who only has to *sign* gets an emailed link and
a verification code, and never makes an account.

**Stage: [`alpha`](roadmap/STAGE.md).** That rung, what it is measured against,
and every reason it is not `beta` are set by the product manager in
[`roadmap/STAGE.md`](roadmap/STAGE.md) and are not restated here. The short
version for someone deciding whether to depend on this today is
[Limitations](#limitations-stated-rather-than-discovered), at the bottom, where
it is meant to be read rather than skipped.

---

## Read this first: this repository contains two backends

There are **two complete, independent server implementations of one product**
in this tree. They are not a frontend and a backend, and they are not a v1 and
a v2. Each one implements the whole product on its own.

| | [`service/`](service/) | [`backend/`](backend/) |
| :--- | :--- | :--- |
| **What it is** | Cloudflare Worker · Durable Object (SQLite) store · R2 for documents · serves `frontend/dist` through the `ASSETS` binding | FastAPI (Python 3.12) · SQLAlchemy · Alembic · PostgreSQL · files on a mounted volume |
| **Does it serve users?** | **Yes.** `service/wrangler.jsonc` claims `sign.pumasi.ai` as a `custom_domain`, and that host answers with this tree's error bodies. | **No.** Nothing in production reaches it. |
| **What CI runs against it** | the `service` job | the `backend` and `e2e` jobs |
| **Its design docs** | [`spec/`](spec/) — one numbered folder per change, with frozen acceptance cases | [`docs/superpowers/specs/`](docs/superpowers/specs/) |
| **How it deploys** | `wrangler deploy` from `service/` | Docker image → Railway (see [below](#deploying-backend--railway-not-what-users-reach)) |

**Which of the two *is* Pumasi Sign is an open question** —
[`pumasi/DECISIONS.md`](https://github.com/pumasi-ai/pumasi/blob/main/DECISIONS.md)
**Q-018** — and it belongs to the steward. This file does not answer it, and
neither should a change you make: do not delete either tree, re-point the
domain, or migrate data on your own authority.

What is *not* in dispute is which of the two answers the domain, and it takes
one command to re-measure:

```console
$ curl -s -X POST https://sign.pumasi.ai/api/auth/dev-login
{"error":"Endpoint not found"}
```

`POST /api/auth/dev-login` is a FastAPI route
([`backend/app/routers/auth.py`](backend/app/routers/auth.py)). The body that
comes back is the worker's — FastAPI answers `{"detail": …}`, never
`{"error": …}`. Measured 2026-09-01 at 01:11 UTC.

### Three things that follow, for anyone reading this repository's green checks

- **A green `backend` or `e2e` job is not evidence about production.** Those
  jobs cover a tree no user reaches. `e2e` is the only suite that drives routes
  over HTTP, and it drives that one — so CI can be entirely green over a live
  production defect, and it has been. The `service` job exists because of
  exactly that.
- **The two trees disagree about who may hold an account.** `backend/` gates
  sign-in on `ALLOWED_EMAIL_DOMAINS`, default `pumasi.ai`
  ([`backend/app/config.py:22`](backend/app/config.py#L22),
  [`auth.py:206`](backend/app/routers/auth.py#L206)). The worker's
  `establishSession`
  ([`service/src/durable.ts:664`](service/src/durable.ts#L664)) is a
  find-or-create for *any* verified email, with no domain gate at all. Which
  behaviour is correct is the second half of Q-018. **Fix a bug in the tree you
  were actually asked about**, and say which one in the commit message.
- **Merged is not shipped.** Who carries a merged, gate-passed build to
  `sign.pumasi.ai` is `pumasi/DECISIONS.md` **Q-012**, which is open. Do not
  read a merge, or a green job, as something a user has received.

## Architecture — the tree that serves users

```mermaid
flowchart LR
  U["Browser<br/>sign.pumasi.ai"] --> W

  subgraph CF [Cloudflare]
    W["<b>Worker</b><br/>service/src/worker.ts<br/><i>routing, Office to PDF</i>"]
    DO["<b>Durable Object</b><br/>PumasiSignService<br/>service/src/durable.ts<br/><i>SQLite: users, envelopes,<br/>fields, sessions, audit</i>"]
    A["<b>ASSETS</b> binding<br/>frontend/dist<br/><i>Vue 3 + Vuetify SPA</i>"]
    R2["<b>R2</b><br/>pumasi-sign-documents<br/><i>originals + stamped PDFs</i>"]
    W -->|"/api/* — run_worker_first"| DO
    W -->|"everything else"| A
    DO --> R2
  end

  W --> GR["<b>Microsoft Graph</b><br/>Office to PDF, mail"]
  DO --> GR
  DO --> GM["<b>Gmail</b> service account<br/><i>alternative mail path</i>"]
  W --> GH["<b>GitHub Issues</b><br/><i>in-app feedback</i>"]
```

One worker, one Durable Object class, one bucket. There is no database server
to operate and no container to keep alive. `wrangler.jsonc`'s
`run_worker_first: ["/api/*"]` is load-bearing: without it the assets layer
answers browser navigations to `/api/*` — OAuth redirects and PDF downloads —
with `index.html`.

## What it does, and where each part lives

Every row is in `service/`, the served tree. The claims below, with a stated
falsifier for each, are the product manager's in
[`roadmap/VALUE.md`](roadmap/VALUE.md); this table is the map from claim to
code, not a second copy of the claim.

| Capability | In the served tree, at |
| :--- | :--- |
| SHA-256 of the original bytes, of the completed output, and a certificate page carrying both | [`service/src/core/stamping.ts`](service/src/core/stamping.ts), called unconditionally on the completion path ([`durable.ts:1596`](service/src/durable.ts#L1596)) |
| Field stamping at deterministic PDF coordinates — six primitives (`signature`, `initial`, `name`, `date`, `text`, `checkbox`), with `dropdown`, `radio` and `label` mapped onto `text` | [`stamping.ts:19`](service/src/core/stamping.ts#L19), mapped at [`durable.ts:1579`](service/src/durable.ts#L1579) |
| Envelopes: `draft` · `pending` · `completed` · `cancelled` (shown as "Voided") · `declined` · `expired` | [`service/src/durable.ts`](service/src/durable.ts) |
| An external recipient signs from an emailed link plus a code, with no account — the access token *is* the identity | [`service/src/durable.ts`](service/src/durable.ts), routes under `/sign/t/<token>` |
| Per-owner company name, logo and primary colour on what recipients see, defaulting to `Pumasi Sign` / `#1A56DB` | `org_branding` ([`durable.ts:161`](service/src/durable.ts#L161), [`:822`](service/src/durable.ts#L822)) |
| Reusable templates, private per sender unless `shared`; sending gated by `users.can_send` | [`service/src/durable.ts`](service/src/durable.ts) |
| No meter, no seat, no plan — grepping `service/src` for `quota`, `billing`, `stripe` or `subscription` returns nothing | (the absence is the feature) |
| `docx` · `doc` · `pptx` · `ppt` · `xlsx` · `xls` converted to PDF by Word/PowerPoint/Excel's own rendering, via Microsoft Graph | [`convert/graph.ts:13`](service/src/convert/graph.ts#L13) |
| PNG and JPG uploads embedded into a PDF in-process, with no external service | [`durable.ts:980`](service/src/durable.ts#L980) |
| In-app feedback filed as GitHub issues | [`service/src/feedback.ts`](service/src/feedback.ts) |

Who this is for, and what would falsify each claim:
[`roadmap/VALUE.md`](roadmap/VALUE.md). Competitor facts, cited and dated:
[`roadmap/MARKET.md`](roadmap/MARKET.md) — no number about another vendor
belongs anywhere in this repository unless it is in that file with a source URL
and a fetch date.

---

## Working on `service/` — the deployed tree

Prerequisites: **Node 22**, and a Cloudflare account only if you intend to
`wrangler dev` against real bindings.

```bash
cd service
npm ci
npm run build   # tsc -p tsconfig.json → service/dist; also this tree's ONLY type-check
npm test        # node --test dist/test/*.test.js
npm run dev     # wrangler dev
```

**`npm test` runs the *compiled* tree, and `service/dist/` is `.gitignore`d.**
Without `npm run build` first it matches no files, runs zero assertions, and
exits **0**. That is not a hypothetical — it is why
[`.github/scripts/assert-service-suite-ran.sh`](.github/scripts/assert-service-suite-ran.sh)
exists and why the `service` CI job runs it as a separate step that stays red
if the build step is deleted. Build first locally too. The reasoning is written
up in [`spec/0002/SPEC.md`](spec/0002/SPEC.md).

Bindings and plain vars live in [`service/wrangler.jsonc`](service/wrangler.jsonc).
Secrets are set with `wrangler secret put` and are **never** committed:

| Secret | Purpose |
| :--- | :--- |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google sign-in for senders |
| `MS_OAUTH_CLIENT_ID` / `MS_OAUTH_CLIENT_SECRET` | Microsoft sign-in for senders |
| `MS_GRAPH_TENANT_ID` / `MS_GRAPH_CLIENT_ID` / `MS_GRAPH_CLIENT_SECRET` / `MS_GRAPH_DRIVE_ID` | App-only Graph credentials — notification mail and Office → PDF conversion |
| `GMAIL_SA_KEY` / `MAIL_IMPERSONATE` | Gmail service-account mail path; both must be set for it to be used at all |
| `MAIL_FROM_NAME` | Display name on outgoing mail (defaults to `Pumasi Sign`) |
| `GITHUB_FEEDBACK_TOKEN` | Token the feedback widget files issues with |

### Deploying it

```bash
cd frontend && npm ci && npm run build   # frontend/dist is .gitignore'd — rebuild it first
cd ../service && npm ci && npm run build
npx wrangler deploy                      # or: npm run deploy
```

That is the whole of it: one `wrangler deploy` publishes the worker, the
Durable Object migration and `frontend/dist` together. Two things to know
before you run it.

1. **`frontend/dist` must be rebuilt first.** `wrangler.jsonc` serves it
   through the `ASSETS` binding, so a stale `dist` ships a stale SPA — and
   because it is one bundle, a deploy carries *everything* on `main`, not the
   one change you came for.
2. **Whether you may deploy at all is not a technical question.**
   `pumasi/DECISIONS.md` **Q-012** — who carries a merged build to users — is
   open and is explicitly outside the charter's proceed-on-default rule. A
   green job is not authorisation. Check that entry first.

**Test coverage in this tree is narrow, and you should know that before you
trust a green run.** [`service/src/test/`](service/src/test/) covers the PDF
stamper, `establishSession` and the session cookie, and the envelope lifecycle.
`worker.ts`, R2, mail, feedback, conversion and the OAuth callback are covered
by nothing. Widening it is ranked as item 2 in
[`roadmap/BACKLOG.md`](roadmap/BACKLOG.md) and is the product manager's call,
not a side errand.

## Working on `frontend/` — the SPA both trees serve

```bash
cd frontend
npm install
npm run dev
npm run test:unit        # vitest
npx vue-tsc -b --force   # type-check — the -b is not optional, see below
npm run build            # → frontend/dist
npx playwright test      # e2e, and it drives backend/ — see the ci.yaml e2e job
```

**`vue-tsc` without `-b` checks nothing.** `frontend/tsconfig.json` is a
solution file — empty `files`, two `references` — so `--noEmit` alone has no
program to check and exits **0** on a tree with type errors. Measured against a
deliberately broken file, not assumed; the comment on the CI step records the
experiment.

`frontend/dist` is `.gitignore`d and is served by the worker's `ASSETS`
binding, so it must be rebuilt before any deploy: **a stale `dist` ships a
stale SPA.**

## The merge gate, and what it does not cover

The root [`package.json`](package.json) exists so that
[`pumasi/tools/gate.sh`](https://github.com/pumasi-ai/pumasi/blob/main/tools/gate.sh),
whose step 1 runs `npm test` at the repository root, runs this repository's
real suites. It carries no `version` field, deliberately; read that file's
`description` for why, since it is the honest account and restating it here
would fork it.

```bash
npm test   # frontend vitest + type-check, then the service suite + the ran-nothing guard
```

`backend/`'s pytest suite and the Playwright e2e job are **not** in that
command — they need Postgres and a built container respectively, and are gated
by CI instead.

## CI

[`.github/workflows/ci.yaml`](.github/workflows/ci.yaml), on every push and
pull request, **four jobs**:

| Job | What it runs | Against which tree |
| :--- | :--- | :--- |
| `backend` | `ruff check`, `ruff format --check`, `pytest` against a `postgres:16` service container, with LibreOffice installed | `backend/` |
| `frontend` | `npx vue-tsc -b --force`, `npm run test:unit`, `npm run build` | `frontend/` |
| `service` | `npm ci` → `npm run build` → `npm test` → `assert-service-suite-ran.sh` | `service/` |
| `e2e` | Playwright against a Docker image of the FastAPI app | `backend/` |

`main` is **not** a protected branch, so CI reports and blocks nothing.

---

## The second implementation: `backend/` — FastAPI + Postgres

**Everything from here to the licence note is about `backend/`, which is
accurate about `backend/` and is not what `sign.pumasi.ai` runs.** It is kept
because the tree is maintained, tested and deployable, and because Q-018 has
not been answered. **If you follow this section end to end you will have
deployed something that is not the product** — Q-018 says so in as many words:
a run that follows the Railway path "would deploy a tree no user reaches and
report it as shipped".

Its design docs are [`docs/superpowers/specs/`](docs/superpowers/specs/),
starting with
[`2026-07-30-internal-esign-design.md`](docs/superpowers/specs/2026-07-30-internal-esign-design.md).

### Stack

- FastAPI (Python 3.12) + SQLAlchemy + Alembic + PostgreSQL
- Auth: Microsoft Entra ID SSO (MSAL) or passwordless email magic links, session cookie
- Document conversion: LibreOffice headless (Office, OpenDocument, rtf/txt → PDF); images (png/jpg/gif/webp/bmp/tiff) convert in-process via Pillow/reportlab
- Serves `frontend/dist` itself when present, falling back to `index.html` for any non-`/api` 404 so client-side routes survive a refresh
- Hosting: Railway (single Docker service + Postgres + volume + daily cron)

Layout: `backend/app/routers/` (auth, templates, submissions, signing, files,
users, jobs), plus `models.py`, `storage.py` (files under `DATA_DIR`),
`stamping.py`, `conversion.py`, `graph.py`, `mailer.py`/`notifications.py`,
`sharepoint.py`, `audit.py`.

### Local development

Requires Python 3.12 and a local Postgres for tests. **The schema uses
Postgres-only features — JSONB, TIMESTAMPTZ — so SQLite is never used**, not
even for tests.

```bash
docker run -d --name sign-test-pg -e POSTGRES_PASSWORD=postgres -p 5433:5432 postgres:16
docker exec sign-test-pg psql -U postgres -c "CREATE DATABASE pumasi_sign_test"
```

The test database URL is read from `TEST_DATABASE_URL`, defaulting to the
container above
(`postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test`).

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
ruff check .
ruff format --check .
pytest
```

Office-document conversion tests skip automatically when `soffice`
(LibreOffice) isn't on `PATH` — install
`libreoffice-writer`/`libreoffice-calc`/`libreoffice-impress` to run them
locally. Image conversion is in-process and always tested.

To run the app itself, set up a normal (non-test) Postgres database, create
`backend/.env` from the committed template (its defaults enable dev auth
bypass so you can log in without Entra), apply migrations, and start uvicorn:

```bash
cp .env.example .env   # from backend/; adjust DATABASE_URL if yours differs
alembic upgrade head
uvicorn app.main:app --reload
```

The backend auto-loads `backend/.env` (pydantic-settings), so no `export`s are
needed. Environment variables set in the shell still win over `.env`.

### Environment variables

Local dev values live in `backend/.env.example` (committed, no secrets) — copy
it to `backend/.env`, which the backend auto-loads. Production values live only
in Railway (`railway variables`).

| Variable | Purpose |
|---|---|
| `MS_TENANT_ID` | Entra tenant ID; ID tokens are rejected unless their `tid` claim matches this |
| `MS_CLIENT_ID` | Entra app registration client ID (MSAL auth-code flow) |
| `MS_CLIENT_SECRET` | Entra app registration client secret |
| `MAIL_SENDER` | Address mail is sent from via Microsoft Graph (`Mail.Send`, app-only) |
| `SESSION_SECRET` | Signing key for the session and auth-flow cookies (`itsdangerous`) — generate with `openssl rand -hex 32` |
| `ADMIN_EMAILS` | Comma-separated list of emails auto-granted `is_admin` on first login (and promoted, never demoted, on later logins) |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated email domains allowed to use magic-link email login (default `pumasi.ai`). **The worker has no equivalent gate — see Q-018** |
| `JOB_TOKEN` | Shared secret required in the `X-Job-Token` header by `POST /api/jobs/daily` — generate with `openssl rand -hex 32` |
| `DATABASE_URL` | SQLAlchemy-style Postgres URL, e.g. `postgresql+psycopg://user:pass@host:port/db` |
| `DATA_DIR` | Root directory for uploaded/generated files and backups (default `/data`; the Railway volume mount point) |
| `APP_BASE_URL` | Public base URL of the deployed app (used for the Entra redirect URI and to decide whether session cookies are marked `secure`) |
| `FEEDBACK_EMAIL` | Recipient for in-app feedback submissions (default `legal@pumasi.ai`) |
| `SP_DRIVE_ID` | Microsoft Graph drive ID for the SharePoint archive site (`b!yfEmPUN-7UyS1Z6xZQVh6YppZfIgzWZBnTKWVL9zhK0zexu6vG5qQ5PA-VUSVyeB`) |
| `SP_ARCHIVE_FOLDER` | SharePoint folder name to mirror signed submissions to (`Signed_document_archive`) — deploy code first, set this var, then run the next daily job to backfill |
| `GRAPH_CONVERT` | If truthy, docx/doc/pptx/ppt uploads convert to PDF via Microsoft Graph (Word/PowerPoint's own rendering; needs `SP_DRIVE_ID` + Graph creds), with LibreOffice as automatic fallback. Spreadsheets (xlsx/xls/ods) always use LibreOffice (one-page-per-sheet export) |
| `DEV_AUTH_BYPASS` | If set truthy, enables `/api/auth/dev-login` for local development. **Must never be set anywhere reachable.** |
| `PORT` | Listen port for uvicorn (set automatically by Railway; used by the Docker `CMD`) |

### Docker

```bash
docker build -t pumasi-sign .
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e DATABASE_URL="postgresql+psycopg://postgres:postgres@host.docker.internal:5433/pumasi_sign_test" \
  -e SESSION_SECRET="dev-secret" \
  -e DATA_DIR=/data \
  pumasi-sign
```

The image is a two-stage build: `node:22-slim` builds the frontend SPA, then a
`python:3.12-slim-bookworm` runtime installs LibreOffice
(Office/OpenDocument/rtf/txt → PDF conversion), `postgresql-client` (for the
daily job's `pg_dump` backup), and fonts: `fonts-dejavu` plus
`fonts-noto-cjk`/`fonts-noto-core` (LibreOffice conversion of
Korean/Japanese/Chinese and other non-Latin text), `fonts-nanum`
(`app/stamping.py`'s reportlab fallback font — the Noto CJK TTCs are
CFF-outline and reportlab can't embed them, NanumGothic is TrueType), and
`fonts-liberation`/`fonts-crosextra-carlito`/`fonts-crosextra-caladea`
(metric-compatible substitutes for Arial/Times/Courier, Calibri, and Cambria so
converted Office documents keep their layout instead of reflowing). The
container's `CMD` runs `alembic upgrade head` before starting `uvicorn`, so
migrations are applied automatically on every deploy.

### Deploying `backend/` — Railway, **not** what users reach

Single Railway service built from the repo `Dockerfile` (see `railway.json` for
the build/healthcheck config — healthcheck path `/api/health`), plus a
Railway-managed Postgres database and a volume mounted at `/data`.

Railway project `pumasi-sign` (environment `production`): main service
`pumasi-sign`, Railway Postgres, and cron service `pumasi-sign-cron` (daily
`POST /api/jobs/daily` at 09:00 UTC). The cron service must be deployed with

```bash
railway up deploy/cron --path-as-root --service pumasi-sign-cron --detach
```

— both flags are mandatory; [`deploy/cron/README.md`](deploy/cron/README.md)
explains why.

Connecting the Railway service to the GitHub repo (Settings → Source → Connect
Repo, branch `main`, with **Wait for CI** enabled) makes every push to `main`
deploy automatically; `railway.json` is picked up from the repo root and
migrations run on container start. `railway up` remains available for one-off
deploys of uncommitted work.

<details>
<summary>Initial provisioning (already performed; kept for reproduction)</summary>

1. `railway init` — create the Railway project.
2. `railway add --database postgres` — provision Postgres; Railway exposes its connection string as a reference variable.
3. Attach a volume mounted at `/data` (dashboard, or `railway volume add --mount-path /data`).
4. `railway variables --set "KEY=VALUE"` for every variable in the table above except `PORT` (Railway sets it) and `DEV_AUTH_BYPASS` (left unset). `DATABASE_URL` is the Postgres service's reference variable (`${{Postgres.DATABASE_URL}}`, converted to the `postgresql+psycopg://` form the app expects).
5. `railway up` — build and deploy the Docker image.
6. `railway domain` — generate the public domain, then `railway variables --set "APP_BASE_URL=https://<generated-domain>"` and redeploy.
7. Configure a cron service that runs daily at **09:00 UTC** and calls:

   ```bash
   curl -X POST "https://<domain>/api/jobs/daily" -H "X-Job-Token: $JOB_TOKEN"
   ```

   This triggers `run_daily_job` (`backend/app/routers/jobs.py`): signature reminder emails plus a `pg_dump` and data-directory backup to `/data/backups` (pruned to the newest 14 of each).

`JOB_TOKEN` and `SESSION_SECRET` were generated with `openssl rand -hex 32` and
are set only as Railway environment variables — never committed.

</details>

### Entra app registration (resolved 2026-07-31)

Login and mail for `backend/` both use the **EmailAutomationApp** registration,
client ID `ef91592e-bb34-4e9d-9a07-ae7ef925396d`, in the Pumasi tenant
(`d2c16235-95cb-4ee8-9bd7-4e8db56c9ad4`) — deployed as
`MS_CLIENT_ID`/`MS_CLIENT_SECRET`/`MS_TENANT_ID` on Railway. Configured on the
app registration:

- **Web redirect URI**: `https://sign.pumasi.ai/api/auth/callback` (the app
  moved to the custom domain `sign.pumasi.ai` on 2026-08-01 and the original
  `pumasi-sign-production.up.railway.app` domain was removed; if the domain
  ever changes again, add the new `https://<domain>/api/auth/callback`
  alongside it)
- **API permissions**: `User.Read` (Delegated, for sign-in) and `Mail.Send`
  (Application, for notification emails), with admin consent granted.

Historical note: the original design spec referenced app registration
`5434f64e-4034-46bc-9447-1a4fc442616c`; the decision (2026-07-31) was to reuse
EmailAutomationApp instead, since its credentials were already provisioned and
it already held the Mail.Send grant.

---

## Limitations, stated rather than discovered

`alpha` on this project's ladder means *it works for people who talk to the
builders*. Concretely, at the time of writing, and each one tracked where it
says:

- **A deadline a sender sets is not acted on.** The SPA tells senders that
  without an expiration date an envelope stays open until completed or voided —
  and the worker has no scheduled handler at all:
  `grep -n 'scheduled\|crons' service/src/worker.ts service/wrangler.jsonc`
  returns nothing. [`roadmap/BACKLOG.md`](roadmap/BACKLOG.md) item 1.
- **A merged fix reaches users at no defined time.** Deployment has no owner
  (Q-012). Read [`roadmap/STAGE.md`](roadmap/STAGE.md) §5 before assuming a
  repair on `main` is a repair a user has received.
- **There is no stated retention or backup posture** for the Durable Object
  store or the R2 bucket. "Your data survives" is not a claim this project has
  established. [`roadmap/STAGE.md`](roadmap/STAGE.md) §2.4.
- **This is not a qualified (QES / eIDAS) signature.** It produces an advanced
  electronic signature with a hash-based audit certificate; qualified
  signatures need hardware this product does not touch.
- **The served tree's automated coverage is narrow** — see
  [Working on `service/`](#working-on-service--the-deployed-tree).
- **`main` is not protected**, and CI blocks nothing.

## Licence

**This repository carries no `LICENSE` file** — verified by `ls LICENSE*` at
the commit this paragraph was written against — and therefore grants no rights
to reuse the code. What licence, if any, this project should carry is
`pumasi/DECISIONS.md` **Q-021**, which is open and is the steward's. Nothing in
this file should be read as a grant, and any copy elsewhere that says otherwise
is ahead of the repository, not behind it.
