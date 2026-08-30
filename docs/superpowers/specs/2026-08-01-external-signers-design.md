# External signers — design

Date: 2026-08-01
Status: approved

## Goal

Let external (non-pumasi.ai) recipients sign envelopes. Externals **sign
only** — creating and sending envelopes stays internal. Access is via an
emailed token link plus a one-time email verification code at signing time.
Also adds **decline to sign** for all recipients (internal and external).

## Background (current state)

Today every layer assumes an internal, logged-in signer:

- `Submitter.user_id` is a NOT NULL FK to `users` (`backend/app/models.py`).
- All `/api/sign/*` endpoints require `Depends(current_user)` and
  `submitter.user_id == user.id` (`backend/app/routers/signing.py`).
- Sign links are bare integer IDs (`/sign/{submitter_id}`,
  `backend/app/notifications.py`) — the login requirement is the only secret.
- `ALLOWED_EMAIL_DOMAINS` blocks external addresses at three points:
  magic-link request, magic-link callback (`backend/app/routers/auth.py`),
  and admin user provisioning (`backend/app/routers/users.py`).
- Certificate, audit trail, and name-field stamping all read signer identity
  from the `users` row (`stamping.py`, `completion.py`, `audit.py`).
- The SPA `/sign/:submitterId` route sits behind the global login guard.
- Decline does not exist for anyone.

## Approach

**Unified identity model.** External signers get a real `users` row flagged
`is_external=true`, created when an admin adds them as a signer. They can
never log in; their only access path is a signed token link scoped to one
submitter. Because they are Users, every downstream consumer of identity —
audit actor FK, certificate text, name-field stamping, `Signature.user_id`
storage — works unchanged.

Rejected alternative: guest submitters (nullable `user_id` + email/name
columns on `submitters`). It keeps `users` employee-only but forces
"user or bare email?" branches through stamping, audit, completion,
notifications, and signature storage, and fragments history if a contractor
is later hired.

## Data model (one Alembic migration)

`users`:
- `is_external` BOOLEAN NOT NULL DEFAULT false.

`submitters`:
- `access_uid` VARCHAR(32) UNIQUE NULL — `secrets.token_hex(16)`, generated
  only for external signers at submission creation; the secret in their sign
  link. NULL for internal signers.
- `verification_code_hash` VARCHAR NULL, `verification_code_expires_at`
  TIMESTAMPTZ NULL, `verification_attempts` INT NOT NULL DEFAULT 0.
- `declined_at` TIMESTAMPTZ NULL, `decline_reason` VARCHAR(500) NULL.
- status CHECK gains `"declined"` (now
  `pending | opened | completed | declined`).

`submissions`:
- status CHECK gains `"declined"` (now
  `pending | completed | cancelled | declined`).

`audit_events`:
- event CHECK gains `"declined"`.

Update the matching constants in `models.py`
(`SUBMITTER_STATUSES`, `SUBMISSION_STATUSES`, `AUDIT_EVENTS`).

## Provisioning external signers

`POST /api/users` (admin): drop the hard domain rejection. An
allowed-domain email creates an internal user as today; any other
syntactically valid email creates a user with `is_external=true`. `name` is
required for externals (feeds the certificate and name-field stamping).

Guards that make `is_external` mean "can never log in":

- Magic-link request and callback: reject users with `is_external=true`
  (defense in depth — the domain gate already covers external domains; this
  keeps them out even if `ALLOWED_EMAIL_DOMAINS` is later widened).
- Entra callback: if the matched user has `is_external=true`, a successful
  tenant-gated login **upgrades the row to internal** (`is_external=false`).
  Tenant membership is proof of employment; signing history carries over.
- `ADMIN_EMAILS` promotion in `upsert_user` skips external users.
- `dev-login` is unchanged (dev-only, already gated by `DEV_AUTH_BYPASS`).

UI: Users admin page and the Send-wizard signer picker show an "External"
chip on external users. Adding an unknown external email in the picker
prompts for the person's name.

## External signing flow

1. **Send.** On submission creation, each external submitter gets an
   `access_uid`; their request email links
   `{APP_BASE_URL}/sign/t/{access_uid}`. Internal signers keep
   `/sign/{submitter_id}` and the login flow, unchanged. Reminder emails use
   the same per-signer link builder.
2. **Landing (public).** `GET /api/sign/token/{access_uid}` → envelope
   title, sender name, masked recipient email (`b***@vendor.com`), and the
   submitter's current state. Enough to render "we'll send a code to …".
   404 on unknown uid; if the envelope is no longer signable
   (completed/cancelled/declined) return that state so the page can say so.
3. **Request code.** `POST /api/sign/token/{access_uid}/request-code`
   generates a 6-digit code, stores `sha256(code)` +
   `expires_at = now + 10 min`, resets `verification_attempts` to 0, and
   emails the code to the submitter's address. Limit: 3 sends per submitter
   per 15 minutes (mirror the magic-link limiter), plus a per-IP limit.
4. **Verify.** `POST /api/sign/token/{access_uid}/verify` with the code.
   Constant-time compare against the hash; max 5 attempts per code, then the
   code is invalidated and a new one must be requested. On success: clear
   the code columns and set the **signer cookie** — `itsdangerous`-signed,
   name `sign_signer`, dedicated salt `sign-signer`, payload
   `{"sid": submitter_id}`, `max_age` 4 h, `httponly`, `samesite=lax`,
   `secure` iff HTTPS (same rules as `sign_session`). The response body
   includes `submitter_id` so the SPA can call the regular signing API.
5. **Sign.** Existing endpoints are reused. A new dependency
   `current_signer_principal` resolves EITHER a logged-in session user OR a
   valid signer cookie; `_get_submitter_authorized` authorizes when the
   session user owns the submitter (as today) **or** the cookie's `sid`
   equals the requested submitter id. The principal exposes the submitter's
   `User` row, so signature upload (`signatures/{user.id}/…`), stored-
   signature ownership checks, value validation, completion, finalization,
   certificate, and audit actor all work untouched.
6. **Files.** `GET /api/files/template-pdf/{template_id}` and
   `GET /api/files/signed-pdf/{submission_id}` additionally accept the
   signer cookie when the cookie's submitter belongs to that
   template's/submission's envelope — the sign page needs the former, the
   success-page download the latter. The certificate route stays
   session-only.

The signer cookie grants nothing else: it is a separate salt and a separate
dependency; `/api/auth/me` and all other app APIs still require a session.

## Decline to sign (all signers)

New `POST /api/sign/{submitter_id}/decline`, body
`{"reason": str | null}` (≤500 chars), auth via `current_signer_principal`.
Allowed while the submitter is `pending`/`opened` and the submission is
`pending`; otherwise 409.

Effects, in one transaction: submitter → `status="declined"`,
`declined_at=now`, `decline_reason`; audit event `declined` (actor = the
signer's user, with IP); submission → `status="declined"` (the envelope is
void — remaining signers' GET returns the declined state and their
complete/decline attempts 409). After commit: email the sender with the
signer's name and reason.

Consequences that need no new code: reminder eligibility already requires
`submission.status == "pending"`, so declined envelopes stop reminding;
`cancel` already 409s on non-pending submissions.

UI: a "Decline" button with a reason dialog + confirmation on the signing
page, shown to internal and external signers alike. Envelope list/detail
views render the `declined` status (chip color, timeline entry with reason
visible to the sender).

## Frontend

- New public route `/sign/t/:accessUid` (`meta: { public: true }`) →
  `ExternalSignView.vue`, rendered with minimal chrome (no nav/app shell —
  route meta consulted by `App.vue`). States: landing/request-code → enter
  code → sign → done / declined / blocked (completed/cancelled/expired).
- Extract the field-filling/signature UI from `SignView.vue` into a shared
  `SigningForm` component used by both views. Replace the `auth.me?.name`
  dependency for name-type fields with the signer name returned by
  `GET /api/sign/{submitter_id}` (add it to `SignerViewOut` if absent).
- External-page API calls use `skipAuthRedirect` so a 401/403 never
  hard-redirects to `/login`; errors render inline (e.g. "code expired",
  "session expired — request a new code").
- Send wizard: picker shows "External" chip; new-external entry collects
  name; the confirmation step notes which recipients are external.

## Security

- `access_uid` is 128-bit random → no enumeration; unknown uids 404.
- Codes: hashed at rest, 10-min expiry, 5 attempts, 3 sends/15 min,
  constant-time comparison.
- Per-IP rate limits on all three public endpoints (in-process limiter,
  following the feedback-endpoint precedent).
- Signer cookie: scoped payload, distinct salt, 4 h TTL, httponly,
  samesite=lax; state-changing routes are POST-only (existing CSRF posture).
- Completion email to external recipients attaches the signed PDF as today
  but omits the `/envelopes/{id}` portal link (login-only surface).
- Audit: `opened`/`signed`/`declined` events for externals carry the real
  user actor and client IP exactly as for internal signers.

## Testing

Backend (pytest, Postgres):
- Provisioning: external domain → `is_external=true`; name required;
  allowed domain unchanged.
- Login guards: external user cannot obtain a magic link or session; Entra
  upgrade path flips the flag.
- Token flow: landing states, code request + resend limit, expiry, wrong
  code lockout at 5, verify sets cookie, signing completes end-to-end,
  certificate lists the external signer, cookie cannot access other
  submitters or non-sign APIs.
- Decline: state transitions, 409 matrix, audit event, sender email,
  reminders stop.
- Existing internal-flow tests pass unchanged.

E2E (Playwright): external happy path — send to external, extract link +
code via the mailer capture pattern, verify, sign, sender sees completion.
One decline path.

## Out of scope (YAGNI)

External senders or portal/history for externals, sequential signing order,
sender-set access codes, SMS verification, notifying co-signers on decline,
CORS (external page is served same-origin by the backend like the rest of
the SPA).
