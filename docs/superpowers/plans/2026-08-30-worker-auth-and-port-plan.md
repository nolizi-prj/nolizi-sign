# Worker auth hardening, and what still separates the worker from the product

2026-08-30. The Cloudflare worker (`service/`) is the Pumasi-purpose rewrite of
the internal FastAPI app. This records what was fixed today and the honest gap
that remains.

## Fixed today (deployed to sign.pumasi.ai)

The worker's auth layer was a demo shell, live on the public internet:

- The login response returned the verification code (`demoCode`) to the caller,
  and accepted `000000`/`123456` as universal codes.
- No sessions existed; `/api/auth/me` returned the first user in the database.
- Every endpoint was unauthenticated; `GET /api/submissions` listed everyone's
  envelopes — including signer tokens, so anyone could sign as anyone.
- No email was ever sent; codes went to console.log.

Now: cookie sessions (`sign_session` for owners, `sign_signer` scoped per
submitter), codes and invitations and completion notices sent via Gmail
(service account, `GMAIL_SA_KEY`/`MAIL_IMPERSONATE` worker secrets), all owner
endpoints scoped by session user, signer endpoints scoped by verified-code
cookie, 60s resend guard. Verified end-to-end in prod: login code email →
create/send envelope → invitation email → landing → signer code email →
verify → signature upload → complete → stamped PDF with audit certificate →
completion emails.

## The gap: frontend contract vs worker API

The Vue frontend is the mature FastAPI-era app (~40 endpoints). The worker now
implements, verified against the real UI in prod (2026-08-30, second pass):

- the signer's full path (`/api/sign/token/*`, `/api/sign/:id`
  signature/complete/decline, `/api/files/*`), auth, branding;
- the sender flow the wizard speaks — recipient directory (`GET/POST /users`),
  `POST /submissions/adhoc` (multipart) + `adhoc/merged-document` (PDF/PNG/JPG
  merge), template-mode `POST /submissions`, drafts, `PATCH`, `DELETE`;
- dashboard/envelope parity — `SubmissionOut` with template brief, sender,
  submitters (CC flags, order groups), `?mine=sent|sign`, `/events`,
  `/form-data`, `send`, `remind`, `cancel`, `archive`, `unarchive`, `copy`,
  per-submitter `resend`. Dashboard, envelope detail (activity timeline, form
  data), and the send wizard all render and flow against it.

Still missing, in the order they block the product:

1. **Template builder** — template CRUD + sharing + build view contract
   (list/create exist; builder-view parity, sharing, copy/archive do not).
   `save-as-template`, `retry-completion`, `replace-document` return 501.
2. **Users/admin** — multi-seat orgs. Today one user = one workspace;
   recipients are a per-owner address book, not accounts.
3. **Attachments** — attachment fields (`/sign/:id/attachment`), stored files.
4. **Storage limits** — PDFs live as DO SQLite blobs; uploads are capped at
   1.5MB (2MB/row ceiling). R2 binding exists (`storage/r2.ts`) but is
   unwired. Move blobs to R2 before real documents arrive.
5. **OAuth sign-in** — LoginView's Google/Microsoft buttons were removed until
   the worker implements the endpoints; email codes are the only door.

Single global DO (`pumasi-sign-main`) is fine at this scale; per-org sharding
(the booking pattern) when usage justifies it.

Stage: **under construction**. Not linked from anywhere public-facing yet.
