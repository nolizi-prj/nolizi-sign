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
implements the signer's full path in that contract (`/api/sign/token/*`,
`/api/sign/:id`, `/api/files/document-preview|signed-pdf|signature`) plus auth,
branding, templates-lite, and submissions-lite. Still missing, in the order
they block the product:

1. **Sender flow the UI actually uses** — `POST /submissions/adhoc`,
   `merged-document`, `PATCH /submissions/:id`, per-submitter resend. The API
   `POST /api/submissions` works (that's what the E2E used) but the SendView
   wizard speaks adhoc/draft.
2. **Dashboard/envelope views** — `SubmissionOut` shape parity (counts,
   archived, drafts), `/submissions/:id/{copy,archive,unarchive,void}`.
3. **Template builder** — template CRUD + sharing + build view contract.
4. **Users/admin** — multi-seat orgs. Today one user = one workspace.
5. **Attachments** — attachment fields (`/sign/:id/attachment`), stored files.
6. **Storage limits** — PDFs live as DO SQLite blobs (2MB/row ceiling);
   R2 binding exists (`storage/r2.ts`) but is unwired. Move blobs to R2 before
   real documents arrive.
7. **OAuth sign-in** — LoginView's Google/Microsoft buttons were removed until
   the worker implements the endpoints; email codes are the only door.

Single global DO (`pumasi-sign-main`) is fine at this scale; per-org sharding
(the booking pattern) when usage justifies it.

Stage: **under construction**. Not linked from anywhere public-facing yet.
