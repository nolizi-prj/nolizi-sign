# INTENT 0011 — never complete an envelope without an executed document

## Problem

The production Worker currently marks an envelope `completed`, writes a
completion event, and sends completion mail when the original document cannot be
loaded. The signed-PDF route then returns 404. `spec/0010` froze this behavior as
A-608 without endorsing it.

The frontend already presents an honest recovery state when every signer is done
but the envelope remains pending, and already calls
`POST /api/submissions/:id/retry-completion`; the Worker returns 501 for that
route.

## Intended outcome

- A missing original never produces a `completed` envelope or completion notice.
- The last signer receives an actionable failure while their signature remains
  recorded.
- The sender can retry completion without asking signers to sign again.
- A successful retry creates exactly one executed document and one completed
  audit event.
- Retrying an already completed envelope is safe and does not stamp or notify a
  second time.

## Out of scope

Replacing a permanently missing original, changing R2 configuration, deploying,
and repairing the separately recorded initials behavior.

