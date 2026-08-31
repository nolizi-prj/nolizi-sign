# INTENT — spec/0006 · A finished envelope stops changing

**Written 2026-08-31 by the coder seat of job `0058`, before the spec.**
Charter §2.1: one page, plain language, no clause numbers, no test IDs.
Its 24-hour window is `pumasi/DECISIONS.md` Q-030.

## What we understood you to want

An envelope that has reached its end — signed and completed, refused by a
signer, or voided by its sender — should **stay** at its end. Today the
worker that answers `sign.pumasi.ai` lets three different requests reach in
afterwards and change it anyway, and each one also writes a fresh line into
the audit trail as though the change were legitimate.

You want the three doors shut.

## Who it is for

Everyone whose name is on an envelope. The sender who voided the wrong one and
the counterparty who signed the right one both depend on the record saying one
thing rather than two.

## What "working" will mean, in your terms

- A completed agreement cannot be voided after the fact. The request comes back
  refused and **nothing about the envelope changes** — not its status, not its
  audit trail.
- A completed agreement cannot be signed a second time by somebody who was only
  copied on it. Today a CC recipient can, and doing so re-runs the completion
  machinery and stamps a second "completed" line into the history of an
  agreement that was already finished once.
- Somebody who has already signed cannot then refuse. An envelope that has
  already ended cannot be refused again. And a signer cannot refuse before it
  is their turn.

In one sentence: **after the envelope is finished, the three ways to change it
all answer "no" and leave the record alone.**

## What we are deliberately not building

- **A way to void a completed agreement on purpose.** If a sender ever does
  need to undo an executed agreement — signed in error, superseded by a newer
  one — that is a new capability with its own button, its own word in the audit
  trail and its own design. It is not this. This change only stops the
  accidental version, which no screen in the product offers and which nobody
  asked for.
- **Anything about deadlines.** The product still tells senders an envelope can
  expire and the worker still never expires one. That is a separate, ranked
  item and this change does not touch it.
- **Any wider test coverage** of the worker than the cases already written.

## Does this take anything away from anyone?

**No, and we checked rather than assumed.** The "Void envelope" button in the
shipped app is only drawn for an envelope that is still pending or still a
draft, so there is no path through the product by which a person voids a
finished one. The refusal route has no button at all — the app never calls it.
Both are reachable only by addressing the API directly. So this change makes
the service agree with a rule the app has been enforcing all along.

## What we are unsure about, and what we will assume if you say nothing

1. **Is refusing the right answer, rather than quietly ignoring the request?**
   *Assumption if silent:* refuse, and say so with an error. Every neighbouring
   transition in the same file already refuses rather than no-ops, and a silent
   success would tell a sender their envelope was voided when it was not.

2. **Should a signer be able to refuse before their turn comes?**
   *Assumption if silent:* no. Refusing is a signing act, it is invited by the
   same email at the same moment, and the signing route already requires the
   turn. Nobody can currently reach the page early anyway.

3. **Is it acceptable that a finished envelope answers a signature attempt and
   a refusal attempt with two different refusal codes** — `410` for the
   signature, `409` for the refusal?
   *Assumption if silent:* yes, and it is deliberate rather than overlooked.
   `410` is what the signing route already returns and changing it would alter
   an answer the app is reading today; `409` is what the voiding and refusing
   routes' neighbours return. Both mean refused and neither is a wrong write.
   The coder seat flags it as the one place the outcome is not fully uniform.

## What could go wrong

An automated caller outside the product that today relies on being able to
void or refuse a finished envelope would start getting an error. We know of
no such caller, and the change is a `git revert` away from undone.
