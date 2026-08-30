# Feedback button — design

Date: 2026-08-01
Status: approved (brainstormed with Pumasi Team)

## Goal

Let anyone using Pumasi Sign — on any page, logged in or not — send
feedback about the app. Each submission is emailed to `legal@pumasi.ai`
via the existing Microsoft Graph mailer. No GitHub integration (considered
and rejected: email-only was chosen; issues get filed by hand).

## Decisions made during brainstorming

- **Audience**: anyone on any page (login page, signing pages, dashboard).
  No authentication required to submit.
- **Content**: only what the user provides — a free-text message plus an
  optional screenshot. Deliberately **no** auto-attached context (no page
  URL, no user identity, no browser info).
- **Delivery**: email only, to a configurable recipient defaulting to
  `legal@pumasi.ai`. Reuses `app.mailer`.

## Frontend

- `App.vue`: add a "Feedback" button to the app bar, **outside** the
  `v-if="auth.me"` block so it renders on every page.
- Clicking opens a `v-dialog` (new component
  `frontend/src/components/FeedbackDialog.vue`) containing:
  - required textarea, max 5,000 characters, with a counter;
  - optional image attach via `v-file-input`, accepts `.png`/`.jpg`
    (`image/png`, `image/jpeg`), client-side max 3 MB;
  - Cancel and Send buttons; Send disabled while empty or submitting.
- Submit sends `multipart/form-data` (`message` text field, optional
  `screenshot` file field) to `POST /api/feedback` using the shared `http`
  util.
- On success: close dialog, clear fields, show the existing UI-store
  snackbar ("Thanks for the feedback!").
- On error: keep the dialog open and show the server's error message
  inline (alert inside the dialog).

## Backend

New router `backend/app/routers/feedback.py`, registered in the app like
the existing routers.

`POST /api/feedback` — no auth dependency.

Request: `multipart/form-data` with `message` (str, required) and
`screenshot` (file, optional).

Validation (in order):

| Check | Failure response |
|---|---|
| `message` non-empty after strip, ≤ 5,000 chars | 400 |
| `screenshot` content type is `image/png` or `image/jpeg` | 415 |
| `screenshot` ≤ 3 MB (Graph sendMail total request cap is 4 MB) | 413 |
| per-IP rate limit: 5 submissions per rolling 10 minutes | 429 |

Rate limiting is a module-level in-memory dict of
`ip -> deque[timestamps]` — deliberately simple; single-process uvicorn on
Railway makes this sufficient. Not persisted; restarts reset it.

On success: call `mailer.send(settings, to=[settings.feedback_email],
subject="Pumasi Sign feedback", html=<escaped message as HTML>,
attachments=[(filename, bytes, content_type)] if screenshot)`.

- `mailer.send` returning `True` → `204 No Content`.
- `mailer.send` returning `False` (mail outage / not configured) →
  `503` with detail "Could not send feedback, please try again later."
  We do not accept-and-drop; the user should know delivery failed.

The email body is the user's message, HTML-escaped, with line breaks
converted to `<br>`. Nothing else is added to the body.

New setting in `config.py`: `feedback_email: str = "legal@pumasi.ai"`
(env var `FEEDBACK_EMAIL`). Document in README's env-var table.

## Mailer change

`_build_message_body` currently hardcodes attachment
`contentType: "application/pdf"`. Change the attachments parameter from
`(filename, bytes)` pairs to `(filename, bytes, content_type)` triples
throughout `mailer.send`. Update the existing call sites (in
`notifications.py`) to pass `"application/pdf"` explicitly. No behavior
change for existing emails.

## Error handling summary

- Mail failure never raises (existing `mailer.send` contract); the
  endpoint translates `False` into 503.
- All validation errors return specific 4xx codes with human-readable
  `detail`; the dialog displays them.
- Nothing about the submission is logged beyond the mailer's existing
  generic failure logs (consistent with the mailer's "never log bodies or
  recipients" rule).

## Testing

Backend (`backend/tests/test_feedback.py`):
- happy path with mailer mocked: asserts recipient = settings value,
  subject, body contains escaped message, attachment triple passed;
- message empty / too long → 400;
- wrong screenshot type → 415; oversized screenshot → 413;
- 6th submission from one IP within window → 429;
- mailer returns `False` → 503.

Mailer tests: update existing attachment tests for the
`(name, bytes, content_type)` triple; add one asserting the content type
lands in the Graph payload.

Frontend: `npx vue-tsc --noEmit` passes. No new Playwright e2e.

## Out of scope

- GitHub issue creation (rejected during brainstorming).
- Screenshot storage on the server — the image goes into the email only.
- Feedback persistence in Postgres.
- Multi-process-safe rate limiting.
