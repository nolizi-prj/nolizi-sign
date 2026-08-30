# Email magic-link login (internal only)

Date: 2026-07-31
Status: approved

## Goal

Add a passwordless email login alongside the existing Microsoft Entra SSO so
Pumasi employees can sign in with just their work email. Internal use only —
no external accounts. No passwords are stored, so there are no
forgot-password, password-reset, or signup-verification flows.

## Decisions (made with the user)

- Mechanism: **magic link** (not OTP code, not passwords).
- Coexistence: **SSO stays primary**; email login is a second option on a new
  login page. Restricted to `@pumasi.ai` addresses via config.
- Scope: internal only. External signing/token-link features are explicitly
  out of scope.

## Backend

New config setting:

- `ALLOWED_EMAIL_DOMAINS` — comma-separated, default `pumasi.ai`. Lowercased
  and trimmed like `ADMIN_EMAILS`.

Two new endpoints in `backend/app/routers/auth.py`:

### `POST /api/auth/email/request`

Body: `{ "email": str, "next": str | null }`.

1. Normalize email (lowercase, trim). If its domain is not in
   `ALLOWED_EMAIL_DOMAINS`, still return the generic 200 response — do not
   reveal eligibility.
2. Rate limit: max 3 sends per email address per 15 minutes (in-process
   store; acceptable because the app runs as a single uvicorn process).
   Over-limit requests also return the generic 200.
3. `next` is validated with the existing `_is_safe_relative_path`; invalid
   values fall back to `/`.
4. Build a token with a new `itsdangerous.URLSafeTimedSerializer` keyed on
   `SESSION_SECRET`, salt `sign-magiclink`, payload `{"email": ..., "next": ...}`.
   The serializer's own timestamp provides issue time and expiry.
5. Send mail via the existing Graph mailer: subject and body state the link
   expires in 15 minutes; link is
   `{APP_BASE_URL}/api/auth/email/callback?token=...`.
6. Response is always `{"ok": true}` (generic), except 502 if the mailer
   itself fails for an eligible address.

### `GET /api/auth/email/callback?token=...`

1. Verify the token with `max_age=900`. On signature/expiry failure, redirect
   to `/login?error=expired`.
2. Single-use enforcement: new nullable column `users.email_login_min_iat`
   (TIMESTAMPTZ). Reject (same redirect) if the token's issue time is `<=`
   the stored value for that user. On success, store the token's issue time.
   A used link — or any older outstanding link — is dead immediately.
3. Re-check the domain against `ALLOWED_EMAIL_DOMAINS` (config may have
   changed since issuance).
4. Upsert the user with the existing `upsert_user` (admin promotion from
   `ADMIN_EMAILS` applies; `entra_oid` stays untouched). For a first-time
   user, `name` defaults to the email's local part.
5. Set the same `sign_session` cookie as the SSO callback and redirect to the
   validated `next` path.

One Alembic migration adds the column.

## Frontend

New public route `/login` (`LoginView.vue`):

- Primary: "Sign in with Microsoft" button → existing
  `/api/auth/login?next=...` redirect.
- Secondary: email input + "Email me a sign-in link" → posts to
  `/api/auth/email/request`, then shows a "check your inbox" state.
- Shows a friendly notice when landed on with `?error=expired`.
- Preserves `next` from the query string in both paths.

Routing changes:

- `router/index.ts` `beforeEach`: unauthenticated users go to
  `/login?next=<fullPath>` instead of hard-redirecting into SSO.
- `utils/http.ts` 401 interceptor: same change.
- `/login` gets `meta: { public: true }` like `/signed-out`.

## Unchanged

Session mechanics (12 h `sign_session` cookie), logout, admin gating,
tenant-locked SSO flow, `DEV_AUTH_BYPASS` dev login, all signing/authz logic.

## Error handling

- Expired / replayed / malformed token → `/login?error=expired` with a
  "request a new link" notice.
- Mailer failure for an eligible address → 502, generic message.
- Ineligible domain or rate-limited → generic 200 (no information leak).

## Testing

Backend (pytest, Postgres, mailer mocked):

- request: eligible domain sends mail; ineligible domain sends nothing but
  returns 200; rate limit stops the 4th send; unsafe `next` falls back to `/`.
- callback: happy path sets session and creates/updates the user; expired
  token rejected; replayed token rejected; second older link rejected after a
  newer one is used; tampered token rejected.

Frontend: `vue-tsc --noEmit` and `npm run build` in CI as today.
