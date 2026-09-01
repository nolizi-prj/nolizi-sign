# INTENT — spec/0007 · The expiration date starts meaning something

**Written 2026-09-01 (UTC) by the coder seat of job `0065`, before the spec.**
Charter §2.1: one page, plain language, no clause numbers, no test IDs.
Its 24-hour window is `pumasi/DECISIONS.md` Q-035.

## What we understood you to want

When somebody sends a document for signature, the app offers them a deadline.
It asks for the date, refuses a date in the past, shows the date back on the
envelope, and tells them in plain words what leaving it blank would mean:
*"Without an expiration date, the envelope stays open until completed or
voided."*

The service behind that screen has never done any of it. A deadline is stored
and displayed and nothing else. A person holding a signing link from an email
can open a document whose deadline passed months ago and sign it, and the
envelope completes as though nothing were wrong.

You want the date to mean what the screen says it means.

## Who it is for

The sender, first. They set a deadline because they wanted the offer to stop
being open — a quote that expires, an offer letter with a reply-by date, a
consent form for an event that has happened. Right now they believe the
document closed itself and it did not.

And the person signing, second — because a document that says it expired on a
date and can still be signed after it is a document nobody can rely on either
way.

## What "working" will mean, in your terms

- **An envelope whose deadline has passed stops being signable.** The signing
  link still opens, and it says the envelope expired instead of asking for a
  signature.
- **The envelope says so on the sender's screen too** — the word "Expired",
  next to the others, in the same list, with a line in the envelope's history
  saying when it happened.
- **Nothing else about it changes.** Nobody's document is deleted, nothing
  already signed is undone, and an envelope with no deadline is untouched
  forever, exactly as the screen promises.
- **A deadline still in the future does nothing at all.**
- **The sender can still change the deadline while the envelope is live.**
  Today the "edit expiration and reminders" pencil says *"Envelope settings
  updated."* and then quietly changes nothing — we found that while measuring
  this, and it stops being harmless the moment the date starts closing
  envelopes.

In one sentence: **the deadline the app asks for is the deadline the service
keeps.**

## What we are deliberately not building

- **No email.** Nobody is told their envelope expired — not the sender, not
  the signers. The app has never promised anyone a message about this, and
  sending mail on a sender's behalf is a bigger commitment than the one this
  change is making. The envelope's own history and the sender's dashboard
  carry the fact, silently.
- **No reviving an expired envelope.** Once it has expired it is finished, the
  same way a voided or a declined one is finished. The sender's route is the
  "Copy" button the product already has, which makes a fresh draft with no
  deadline on it.
- **No expiring of drafts.** A draft was never sent to anybody. Expiring one
  would take away a document the sender is still writing.
- **Nothing about reminders** beyond making the existing settings dialog
  actually save, and nothing about any other envelope status.

## Does this take anything away from anyone?

**Yes, and that is the point — so it is stated rather than buried.** Somebody
who could have signed a lapsed document will no longer be able to. That is
what a deadline is, it is what the sender asked for when they set one, and it
is what the app already tells both of them is happening. Nothing already
signed is affected: an envelope that completed before its deadline stays
completed, and the sealed PDF and its certificate are never touched.

**One residual we are choosing rather than discovering.** The closing happens
on a timer that runs every hour, not at the exact second the deadline passes.
So there is a window of up to an hour in which the service would still accept
a signature the app's own signing page already refuses to offer. We picked an
hour over a day for exactly that reason, and we are saying so out loud instead
of implying the deadline is enforced to the second.

## What we are unsure about, with the answer we will assume

1. **How often the timer should run.** *Assumed: every hour, on the hour, UTC.*
   The other implementation of this product runs its daily job at 09:00 UTC;
   we are not copying that, because the interval is exactly the length of time
   during which the screen's promise stays false, and hourly costs nothing
   here.
2. **Whether anyone is emailed.** *Assumed: no.* See above.
3. **What the history line is called.** *Assumed: "expired"*, written by the
   service itself rather than attributed to a person, because no person did
   it.
4. **Whether an expired envelope is as final as a completed one.**
   *Assumed: yes.* It refuses a signature, a refusal and a void, exactly as a
   completed, declined or voided envelope already does.
