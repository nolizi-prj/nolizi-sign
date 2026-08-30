# Pumasi Sign — Internal E-Signature Service — Design

Date: 2026-07-30
Status: Approved by Pumasi Team (admin@pumasi.ai) in brainstorming session

> **Historical snapshot (note added 2026-08-09).** This founding doc is kept
> as-is for context, but several sections are superseded by later specs:
> external signers (PR #28, `2026-08-01-external-signers-design.md`),
> per-send fields (ad-hoc envelopes), and sequential signing order
> (PR #36/#38, `2026-08-05-send-flow-features-design.md`) all shipped
> despite appearing under "Out of scope"; the roles model is now
> `users.can_send` (default true, admin-revocable — not admin-only
> sending); and the data model has grown well past the six tables below
> (declined status, certificates, per-user archive, CC-as-submitters,
> external verification columns). Trust the newer specs and the code.

## Purpose

A minimal internal DocuSign-style web service for collecting signatures from
Pumasi employees on internal documents (HR forms, policy acknowledgments,
internal approvals). Not for external parties. Optimized for simplicity of
operation: one service, one database, one volume.

## Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Signers | Pumasi employees only |
| Auth | Microsoft Entra ID SSO (Office 365 tenant), auto-provision users on first login |
| Signing UX | Sender places signature/name/date/text/checkbox fields on PDF pages; signers fill in place |
| Workflow | Multiple signers per submission, any order; complete when all have signed |
| Templates | Admins upload Word/Excel/PDF → converted to PDF → fields placed once → reused per send |
| Notifications | Email via Microsoft Graph API (`Mail.Send`, app-only), reminders every 3 days (max 3), completion email with signed PDF |
| Audit | Appended audit page (name, email, timestamp, IP), append-only event log, immutable signed PDFs |
| Roles | `is_admin` users create templates and send; all employees can sign |
| Stack | FastAPI (Python) + Vue 3 + PostgreSQL |
| Hosting | Railway: single service + Postgres + volume; daily cron for reminders/backup |
| Storage | Railway volume now, behind a `FileStorage` interface so S3/R2 can be swapped in later |

Reference implementations studied: DocuSeal (Template→Submission→Submitter
model, JSON field coordinates, Vue WYSIWYG builder), Documenso (single-container
Railway deployment, audit trail shape). Patterns borrowed, no code copied.

## Architecture

Single Railway service. FastAPI serves the JSON API under `/api` and the built
Vue 3 SPA as static files. The container includes LibreOffice headless for
docx/xlsx→PDF conversion. Railway Postgres and a mounted volume (`/data`)
complete the deployment. A Railway cron job hits a protected endpoint daily for
reminders; backups dump DB + files to a dated archive on the volume.

```
Browser (Vue 3 SPA)
   │ HTTPS
   ▼
Railway service: FastAPI ──► Postgres
   │        ├──► Volume /data (originals, PDF renditions, signature images, signed PDFs, backups)
   │        ├──► LibreOffice headless (subprocess, office→PDF)
   │        └──► Microsoft Graph API (sendMail as admin@pumasi.ai)
Railway cron (daily) ──► POST /api/jobs/daily (reminders + backup), guarded by job token
```

### Backend modules

- **auth** — Entra ID OAuth2 auth-code flow (MSAL). Session cookie (signed,
  HttpOnly). Tenant-restricted. First login creates the `users` row. `is_admin`
  seeded via `ADMIN_EMAILS` env var; admins can toggle the flag for others in
  the UI. `DEV_AUTH_BYPASS=1` enables a local-only fake login (never set in
  prod).
- **conversion** — upload (pdf/docx/xlsx, max 25 MB) → canonical PDF rendition
  via LibreOffice headless; PDFs pass through. Failures (corrupt, encrypted)
  reject the upload with a clear error; nothing persisted.
- **stamping** — on completion, `pypdf` + `reportlab` draw each signer's
  signature image / name / date / text at stored normalized coordinates, then
  append an audit page. Output stored as the immutable signed PDF.
- **mailer** — Graph API `sendMail` (client credentials). Retries with
  exponential backoff (3 attempts). Per-submitter send status recorded.
- **storage** — `FileStorage` protocol: `save(key, bytes)`, `open(key)`,
  `delete(key)`, `exists(key)`. One implementation now: `LocalVolumeStorage`
  rooted at `/data`. S3 implementation is a later drop-in.

### Frontend views (Vue 3 + Vuetify, Composition API — cloud-platform conventions)

- **Dashboard** — submissions I need to sign; admins also see sent submissions
  with per-signer status, and the templates list.
- **Template builder** (admin) — pdf.js renders pages; drag-and-drop field
  overlay; define roles (labels like "Employee", "Manager"); assign fields to
  roles; field types: signature, name, date, text, checkbox.
- **Send flow** (admin) — pick template → map each role to an employee → optional
  message → send. Ad-hoc sends create a single-use template under the hood.
- **Signing view** — PDF with the signer's fields highlighted; draw/type
  signature once (stored for reuse); fill remaining fields; confirm.
- **Admin screen** — user list with `is_admin` toggle.

## Data model

- **users** — `id, email (unique), name, entra_oid, is_admin, created_at`
- **templates** — `id, name, created_by → users, original_file_key, pdf_key,
  page_count, fields JSONB, is_adhoc, created_at, archived_at`
  - `fields`: `[{id, type: signature|name|date|text|checkbox, role, page,
    x, y, w, h, required}]`, coordinates normalized 0–1 relative to page size.
- **submissions** — `id, template_id, title, message, status:
  pending|completed|cancelled, created_by, created_at, completed_at,
  signed_pdf_key`
- **submitters** — `id, submission_id, user_id, role, status:
  pending|opened|completed, signed_at, ip_address, values JSONB,
  last_reminded_at, reminder_count, email_status`
  - `values`: `{field_id: value}`; signature values reference a stored image.
- **signatures** — `id, user_id, image_key, created_at` (latest per user reused)
- **audit_events** — `id, submission_id, actor_user_id, event:
  created|sent|opened|signed|reminded|completed|cancelled, ip_address,
  detail JSONB, created_at` (append-only; no update/delete paths)

State machine: submitter `pending → opened → completed`; submission `pending →
completed` (when last submitter completes) or `pending → cancelled` (admin).
Completion side effects (stamp, audit page, emails) run after the status-flip
transaction commits; stamping failure leaves submission `pending` with the
error logged and a retry endpoint.

## Key flows

1. **Template creation**: upload → convert → builder → save fields/roles.
2. **Send**: template + role→user mapping → create submission + submitters →
   `sent` audit events → "please sign" email with direct deep link per signer.
3. **Sign**: deep link → SSO → `opened` recorded → fill fields → confirm →
   `signed` audit event with IP → if last signer, completion pipeline.
4. **Completion**: stamp PDF + audit page → store → email signed PDF to all
   signers + sender → `completed`.
5. **Reminders** (daily cron): submitters pending/opened, ≥3 days since last
   touch, `reminder_count < 3` → reminder email, increment count, audit event.
6. **Cancel** (admin): submission → `cancelled`; signing links show a friendly
   "no longer active" page.

## Error handling

- Conversion errors → 422 with reason; upload discarded.
- Graph send failures → retry ×3 with backoff; `email_status` surfaced to
  admins on the submission page.
- Signing idempotency: completed/cancelled submitters get an "already handled"
  page; double-submit is a no-op.
- All file reads go through storage keys stored in DB; missing files surface
  as 500s with alerting via logs (Railway log drain later if needed).

## Security notes

- Session cookie: signed, HttpOnly, Secure, SameSite=Lax.
- Tenant check on the ID token (`tid` must match `MS_TENANT_ID`).
- Signing endpoints authorize: the logged-in user must be the submitter.
- Admin endpoints authorize on `is_admin`.
- Uploaded files validated by extension + magic bytes; served only through
  authorized endpoints, never as public static files.
- Graph secret, session secret, job token, DB URL: Railway env vars only.

## Testing

- **pytest** (backend): conversion (fixture docx/xlsx/pdf), stamping coordinate
  math, submitter/submission state transitions, auth gates (admin vs signer vs
  outsider), reminder selection query, mailer retry logic (Graph mocked).
- **Playwright e2e** (dev bypass auth): build template → send → sign with two
  users → completed PDF exists and contains audit page.
- CI: GitHub Actions — ruff + pytest on push.

## Deployment

- Railway project `pumasi-sign`: service (Dockerfile), Postgres plugin,
  volume at `/data`, cron schedule for daily job.
- Dockerfile: python slim + LibreOffice + built Vue assets (multi-stage).
- Alembic migrations run on container start.
- Env vars: `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`,
  `MAIL_SENDER=admin@pumasi.ai`, `SESSION_SECRET`, `ADMIN_EMAILS`,
  `JOB_TOKEN`, `DATABASE_URL`, `DATA_DIR=/data`, `APP_BASE_URL`.
- **Manual step (Pumasi Team)**: add redirect URI
  `https://<railway-domain>/api/auth/callback` (type: Web) to Entra app
  registration `5434f64e-4034-46bc-9447-1a4fc442616c`.

## Out of scope (YAGNI)

External signers, sequential signing order, field placement per-send,
fill-in text placeholders in templates, cryptographic PDF certification,
multi-tenant support, mobile apps, webhooks, API for other services.
