# Envelope public UID (non-enumerable watermark/certificate ID)

Date: 2026-07-31
Status: approved

## Problem

The completed-PDF watermark stamps `Pumasi Sign · Envelope #<id> · Completed
<iso>` and the signature certificate prints `Submission: <title> (ID <id>)`,
where `<id>` is the sequential integer primary key of `submissions`. Both
artifacts leave the company: any counterparty holding two signed PDFs can
subtract the numbers and estimate Pumasi's envelope volume. No other surface
leaks the sequential number externally — emails and the SPA never show
"Envelope #N", and API routes/URLs are session-auth-gated to employees.

## Design

### Data model

Add `public_uid` to `Submission` (`backend/app/models.py`):

- `String(32)`, `unique=True`, `nullable=False`
- Generated in Python at creation time: `uuid.uuid4().hex`
- The integer PK is unchanged and remains the key for API routes, URLs,
  foreign keys, and storage paths — those are internal-only and not the leak.

One Alembic migration:

1. Add `public_uid` as nullable.
2. Backfill every existing row with a fresh `uuid4().hex`.
3. Alter to NOT NULL and add the unique constraint.

### Stamping (`backend/app/stamping.py`)

The two externally visible strings switch from the integer ID to the UID:

- Watermark: `Pumasi Sign · Envelope <public_uid> · Completed <iso>`
- Certificate: `Submission: <title> (Envelope <public_uid>)`

The stamping entry points take the UID as a parameter (replacing the
`submission_id` parameter where it was only used for display);
`completion.py` passes `submission.public_uid`.

### API / UI

A UID stamped on a PDF is only useful if it can be looked up, so:

- `SubmissionOut` gains `public_uid`.
- The envelope detail page shows it as a small copyable line.
- No search endpoint — direct DB lookup suffices for rare support cases
  (YAGNI).

### Error handling

Nothing new. uuid4 collision odds are negligible; the unique constraint is
the backstop.

### Testing

- Stamping/completion tests assert the watermark and certificate contain the
  UID and do **not** contain the sequential `#<id>` form.
- Migration backfill is exercised implicitly: the test suite runs
  `alembic upgrade head` against the Postgres test DB.

## Rejected alternatives

- **UUIDs everywhere** (routes, storage keys, frontend): churns every router
  and the SPA for no gain — internal surfaces are auth-gated and not the
  leak.
- **Obfuscated sequential ID** (hashids/sqids): reversible obscurity, ordering
  recoverable if the salt leaks; real randomness is barely more work.
- **Short base32 code** (`CS-7K3M-9QPX-2BTF`): friendlier to read aloud, but
  full `uuid4().hex` matches what DocuSign stamps and was chosen by the user.
