# Send-flow features: sender text, prefilled text, signing order, CC

Date: 2026-08-05. Four requests: (1) write text before sending an envelope;
(2) prefilled text on text inputs; (3) ordered signature collection;
(4) CC recipients. A "Message to signers" box already exists in the send
wizard, so (1) is interpreted as DocuSign-style sender text placed on the
document itself.

## 1+2. Label fields and `default_value`

`FieldDef` gains `default_value: str | None` (≤500 chars) and a new type
`"label"`:

- **label** — sender-authored static text. Role-less (role normalized to
  `""`, never required): exempt from role-mapping validation and from
  `TemplateFieldsUpdate`'s orphaned-role check. Stamped into the final PDF
  unconditionally (drawn with the same text rules as other fields); shown to
  every signer as read-only text at stamped size. Never signable — labels
  are excluded from `_my_fields`, the tour, and value validation.
- **text + default_value** — the send-time prefill. The signing view seeds
  the input with `default_value`; the signer can edit or clear it. Stamping
  uses only the submitted value (a cleared prefill stays cleared).

Builder/compose UI: a "Label" placement button (no role needed) and an
inline input inside text/label boxes for the prefill/label content.

## 3. Signing order

`Submitter.order_index` (int, default 0; equal values sign in parallel —
today's behavior is "everyone at 0"). `SignerIn.order` optional in both
create paths; the send wizard gets a "collect signatures in order" toggle
that assigns the listed order (1, 2, 3…).

Gating, all server-side in terms of the *active group* — the minimum
`order_index` among non-completed submitters:

- `on_submission_created` emails only the active group; later signers keep
  `email_status = NULL` ("not yet asked").
- When a completion doesn't finalize the envelope, a new
  `notifications.on_submitter_completed` emails any newly-active submitters
  whose `email_status` is NULL.
- `POST /complete` 409s for a submitter before their turn;
  `GET /sign/{id}` exposes `my_turn` so the signing page shows a
  "you'll be notified when it's your turn" blocked state instead.
- Reminders (manual and daily) skip submitters outside the active group.
- Replacing a signer emails the replacement only if they're in the active
  group (otherwise the unlock hook emails them later).

## 4. CC recipients

> **Superseded (note added 2026-08-09).** PR #38 (migration
> `f8c4d2a91b60_cc_as_recipients`) replaced this schema wholesale: CCs are
> real `Submitter` rows with `is_cc=true` and role `""`, not a
> `Submission.cc_emails` JSONB list. They're picked as users (provisioned
> by email like signers), carry an `order_index` so copies follow the
> routing, receive a copy notice when their group is due plus the final
> PDF on completion, appear in recipients' Inbox (flagged CC), and are
> excluded from signing routes, completion gating, and reminders. The
> max-10 cap and per-envelope dedupe from this section were re-added at
> creation-validation level on 2026-08-09. The paragraph below is the
> original, obsolete design.

`Submission.cc_emails` (JSONB list of normalized emails, default `[]`, max
10, validated with the existing `EMAIL_RE`). Provided at create time (both
paths) via the wizard's CC chips input; shown on the review step and in
`SubmissionOut`. CCs receive the completion email with the signed PDF
attached — addresses that belong to internal users get the portal link
variant, everyone else the plain variant. CCs get no signing link and no
reminders.

## Migration

One Alembic revision (down_revision `c9d1f6b3e2a7`): `submitters.order_index`
int NOT NULL server_default '0'; `submissions.cc_emails` JSONB NOT NULL
server_default '[]'. Both backward-compatible defaults — existing envelopes
behave exactly as before (single group 0, no CCs).

## Testing

Backend TDD: label schema normalization + role-mapping exemption + stamping;
prefill passthrough; order gating (create emails group 0 only, unlock emails
group 1, early complete 409s, reminders scoped, my_turn flag); CC validation
(bad email 422, cap, dedupe) and completion recipients. Frontend: vue-tsc +
build; existing e2e flows unaffected (all features default off).
