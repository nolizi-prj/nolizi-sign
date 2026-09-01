# SPEC 0007 — The worker keeps the deadline the app asks for

**Intent:** [`INTENT.md`](INTENT.md) · window `pumasi/DECISIONS.md` Q-035.
**Takes:** `roadmap/BACKLOG.md` item **1** at `ba1cea7`, option **(A)**, and
nothing else in that file.
**Does not take:** option (B) (declaring `expires_at` advisory). That option
retracts a promise the SPA makes to senders in words and the entry says it
needs a `DECISIONS.md` question first; none is raised here, because it is not
recommended and is not taken.
**Measured at** `ba1cea7`, by the coder seat of job `0065`, 2026-09-01 UTC.
The packet named `f3c1a92`; `main` advanced to `ba1cea7` under this seat while
job `0064` merged `README.md`. `git diff --stat f3c1a92 ba1cea7` does not list
`roadmap/BACKLOG.md`, so **item 1 is byte-identical at the two SHAs** and this
spec quotes the SHA it actually read.

---

## S0 · The four sub-questions, answered with named defaults

The packet and `BACKLOG.md` item 1 both require these four settled *in the
spec*, by the builder, with named defaults. None is a steward act.

| # | Question | **Default taken** |
| :--- | :--- | :--- |
| **1** | Cron cadence | **Hourly, on the hour, UTC** — `"crons": ["0 * * * *"]`. |
| **2** | How `scheduled` enumerates Durable Objects | **It does not, because there is exactly one.** §S2. |
| **3** | Does an expiry notify anyone | **No. Silence.** §S5. |
| **4** | Audit event name, and `isTerminal()` | **`expired`, system-authored; and yes, `expired` joins `isTerminal()`.** §S4. |

### S0.1 · (1) Cadence — hourly, and why not daily

`backend/`'s `POST /api/jobs/daily` runs at 09:00 UTC. **Q-018 is open**, so
that tree is read here for *shape* — a periodic sweep, driven from outside the
store — and is **not** treated as the answer to the interval.

The interval is chosen from what it costs and what it buys, both measured:

- **What it buys.** The interval *is* the length of time during which the SPA's
  own promise is false — the window in which `POST /api/sign/:id/complete`
  would still accept a signature that `SignView.vue:479` already refuses to
  offer. Daily makes that window up to 24 hours. Hourly makes it up to 1 hour.
- **What it costs.** One `SELECT` and one `UPDATE` against a single SQLite
  store, on one Durable Object (§S2). Twenty-four invocations a day instead of
  one is not a cost this product can measure.

So: hourly. **The residual is stated rather than implied**: this is not
second-accurate enforcement, and §S7 records that as a known limitation in the
release note rather than leaving a reader to assume otherwise.

### S0.2 · (2) Enumeration — the question dissolves on measurement

`BACKLOG.md` item 1 calls this *"the real work in this item"*, on the premise
that *"every envelope lives in one [Durable Object]"* and that `service/` has
no pattern for reaching them all. **Re-measured here, the premise is true only
in the trivial sense, and the consequence does not follow.**

`service/src/worker.ts:130`–`:131`, for **every** `/api/*` request without
exception:

```ts
const id = env.SIGN_SERVICE.idFromName('pumasi-sign-main');
const stub = env.SIGN_SERVICE.get(id);
```

There is **one** named Durable Object instance in this product. `idFromName`
is called with a constant. Every user, session, template, envelope, submitter,
field, signature and audit row in Pumasi Sign lives in that single object's
SQLite store — `durable.ts:126`–`:252` declares one schema and
`PumasiSignService` is the only class in `wrangler.jsonc`'s `durable_objects`
block. There is no per-envelope object, no shard map, and therefore **nothing
to enumerate**.

So the design is:

```
cron trigger (wrangler.jsonc)
  → export default { scheduled() }        (worker.ts)
      → SIGN_SERVICE.idFromName('pumasi-sign-main')   ← the SAME constant fetch() uses
        → stub.fetch(POST /__internal/expire)
          → PumasiSignService.sweepExpired()          (durable.ts)
            → one SELECT, one UPDATE, one audit row per envelope
```

**The one constant is named once and shared.** `worker.ts` gets a
`SIGN_SERVICE_NAME` constant and both the request path and the scheduled path
read it, because two string literals that agree today are
`pumasi/lessons/L-007` waiting to happen — and here the failure mode is a
sweep that runs happily against an empty second store and expires nothing,
which is `L-006` (a green thing that measured nothing) wearing the other hat.

**This is a finding, and it is handed up rather than corrected in
`BACKLOG.md`**, which is the product manager's register and not this seat's to
edit: item 1's stated reason for ranking this as design work — *"there is no
existing pattern in `service/` to copy"* — is right about the absence and
wrong about the difficulty. The item is still correctly ranked; it is simply
smaller than its own text expects, and the effort it was ranked for is instead
spent on §S3 and §S6.

**`CLAUDE.md:107`–`:110` therefore does not change meaning and is not
edited.** The packet made that edit conditional on sub-question (2) changing
what the status list *means*. It does not: `expired` remains *"past its
optional `expires_at` deadline — flipped by the daily job"*, and after this
change a job exists and flips it. The word *"daily"* becomes *"hourly"* in
fact; that single word is `roadmap/STAGE.md` §5's live row and `roadmap/` is
the product manager's, so it is reported in the return block rather than
ticked here.

**Rejected alternative: a Durable Object `alarm()`.** Cheaper to fire, but the
schedule then lives as re-armed state *inside* the object rather than as a
declared line in `wrangler.jsonc`. A missed re-arm is invisible, and nothing in
the repository would tell a reader the sweep is supposed to exist.
`BACKLOG.md` item 1 named a cron trigger; a cron trigger is what this takes.

### S0.3 · (3) Notification — silence

**No mail is sent when an envelope expires**, to anyone.

1. **Nothing in the product promises it.** The SPA's two sentences
   (`SendView.vue:1332`, `EnvelopeDetailView.vue:1104`) promise that a
   deadline closes the envelope. No screen mentions a message.
2. **Sending mail is the one act in this change that no revert undoes.**
   CHARTER Part 0 lists *sending mail* among the acts never suspended
   pre-`launched`. A cron that mails external recipients on a sender's behalf
   is a larger commitment than the one being made, and it is the half of this
   change with no evidence behind it.
3. **The fact is not lost.** It lands in the envelope's audit trail (§S4), in
   the status word on the sender's dashboard, and in `EnvelopeBrowser.vue`'s
   existing `expired` filter — all of which the SPA already renders.

### S0.4 · (4) The audit event, and `isTerminal()`

**The event type is `expired`**, written with the same system actor
`finalize()` already uses for `completed` — `'system@pumasi.ai'` /
`'Pumasi Sign Engine'` (`durable.ts:1609`, `:1617`) — because no person
performed it and attributing it to the sender would be a false record.
`frontend/src/types.ts:127` already declares `"expired"` in `AuditEventType`
and `EnvelopeDetailView.vue:596` already renders it as *"Envelope expired —
its deadline passed before everyone signed"*. **The SPA has been ready for
this event since before the worker could write one**; this spec adds the
writer, not the vocabulary.

**`expired` joins `isTerminal()`** (`durable.ts:109`). An expired envelope is
finished in exactly the sense the other three are: no further transition can
improve the record, and any write after it is destroying a record rather than
making one. The three guards job `0058` merged then cover it with no new code:

| Route | Guard | Expired envelope now answers |
| :--- | :--- | :--- |
| `cancel` (`:1252`) | `isTerminal(sub.status)` | **409** *"This envelope is already closed"* |
| `complete` (`:1452`) | `isTerminal(submission.status)` | **410** *"This envelope is no longer active"* |
| `decline` (`:1513`) | `isTerminal(submission.status)` | **409** *"This envelope is no longer active"* |

That is the packet's *"a fifth terminal state that is not in it is a hole in
work that just merged"*, closed by adding one string to one predicate rather
than by writing a fourth guard.

`send`/`remind` (`:1235`) tests `sub.status !== 'pending'` and already refuses
`409`; it is left alone. `DELETE` is draft-only and unaffected. **`copy`
(`:1269`) is deliberately left unguarded and is the sender's route out**: it
copies any envelope into a fresh `draft` and `:1278` writes `NULL` into the
copy's `expires_at`, so a sender whose envelope lapsed gets a new one with no
deadline in one click.

---

## S1 · The defect, re-read rather than inherited

Line numbers are `ba1cea7`. Re-run by this seat at that SHA:

```
$ grep -n 'scheduled\|triggers\|crons' service/src/worker.ts service/wrangler.jsonc
(no matches)
```

**S1a. What the SPA tells the user, measured at `ba1cea7`.** Line numbers
moved under job `0064`'s `README.md`-only commit? No — `SendView.vue` was
changed by `1338f68`, so the packet's `SendView.vue:1336` is now **`:1332`**.
Re-read here rather than carried:

| Site | Text |
| :--- | :--- |
| `SendView.vue:1325`, `EnvelopeDetailView.vue:1098` | *"The expiration date must be in the future."* |
| `SendView.vue:1332`, `EnvelopeDetailView.vue:1104` | *"Without an expiration date, the envelope stays open until completed or voided."* |
| `EnvelopeDetailView.vue:746` | *"· expires {date}"* |
| `EnvelopeDetailView.vue:777` | *"Its expiration date has already passed — set a new one"* |

**S1b. And what the SPA already does about it, which the entry does not
record.** `SignView.vue:474`–`:485` **already blocks the signer client-side**
on a past deadline, in two branches, and the comment on the first one reads:

```ts
} else if (signRes.data.submission.status === "pending" && expired) {
  // Past-due but not yet swept: the server rejects /complete the same way.
```

**That comment is false at `ba1cea7` and the frontend was written expecting
this spec.** It names *the sweep*. It is the strongest single piece of evidence
that option (A) is the correction the product was designed around, and it is
recorded here because it was not in the entry that ranked the item.

**S1c. The exact harm, and its shape after this change.** A recipient holding
a token link cannot sign a past-due envelope *through the app* — `SignView`
refuses to draw the signing surface. They can sign it by addressing
`POST /api/sign/:id/complete` directly, and frozen case **A-409** drives
precisely that and asserts `200 {"ok":true,"status":"completed"}`. After this
change the sweep flips the envelope to `expired` and `isTerminal` makes that
same call answer **410** — for anything more than an hour past its deadline
(§S0.1's residual).

**S1d. A second, smaller broken promise on the same field, found while
measuring this one — and it is a precondition, not a bonus.**
`EnvelopeDetailView.vue:428`–`:431` PATCHes `expires_at`,
`reminders_enabled` and `reminder_interval_days` to
`PATCH /api/submissions/{id}`. The worker's handler (`durable.ts:1206`–
`:1216`) writes **`title` and `message` only** and silently discards all
three, then returns the unchanged row; the dialog closes on
*"Envelope settings updated."* and the date reverts on reload. Grep for the
two reminder columns in `durable.ts` finds them written at `:1063`, `:1099`
and `:1276` — three `INSERT`s — and **never in an `UPDATE`**.

Today that costs nothing, because the deadline costs nothing. **The moment
this spec makes the deadline binding, a sender who tries to extend one before
it passes is told it worked, and the envelope expires on the old date
anyway** — a trap this change would create. It is fixed here for that reason
and its scope is stated in §S3d rather than left to a reader to bound.

---

## S2 · The sweep

**S2a. `wrangler.jsonc`** gains, as a sibling of `routes`:

```jsonc
"triggers": { "crons": ["0 * * * *"] }
```

**S2b. `worker.ts`** gains a module-level constant, an internal-path refusal
and a `scheduled` export:

```ts
/** The one Durable Object this product has. Named once; §S0.2. */
const SIGN_SERVICE_NAME = 'pumasi-sign-main';

/** Only scheduled() constructs this; a request that arrives over the wire is
 *  refused before any binding is touched. */
const INTERNAL_PREFIX = '/__internal/';
```

`fetch()` refuses `INTERNAL_PREFIX` as its first act after parsing the URL —
before the CORS pre-flight branch, so nothing about the path is observable —
and the `/api/*` forward at `:130` is rewritten to use `SIGN_SERVICE_NAME`.

```ts
async scheduled(_event: ScheduledController, env: Env, _ctx: ExecutionContext): Promise<void> {
  const stub = env.SIGN_SERVICE.get(env.SIGN_SERVICE.idFromName(SIGN_SERVICE_NAME));
  const res = await stub.fetch(new Request(`https://sign.internal${INTERNAL_PREFIX}expire`, { method: 'POST' }));
  if (!res.ok) throw new Error(`expiry sweep failed: ${res.status} ${await res.text()}`);
}
```

**The `throw` is load-bearing.** A `scheduled` handler that swallows a failure
is a cron that reports success having expired nothing, which is
`pumasi/lessons/L-006` at infrastructure scale — the same failure
`.github/scripts/assert-service-suite-ran.sh` exists to stop one level down.
Throwing puts it in Cloudflare's cron invocation log.

**S2c. Why the internal path is not under `/api/`.** `worker.ts` forwards
*every* `/api/*` path to the Durable Object, so a sweep route under `/api/`
would be reachable from the public internet by anyone who guessed it. Putting
it under `/__internal/` and refusing that prefix in `fetch()` means the only
caller is `scheduled()`, which reaches the object through `stub.fetch()` and
never through the worker's own `fetch()`.

The refusal is a plain `404 {"error":"Not found"}`. **Nothing here is
protected by obscurity** — this repository is public-by-intent (CHARTER P2)
and the path is written down three lines above the guard. The guard is the
protection; the path is just a name.

**This also keeps A-409 true.** `/api/jobs/daily` remains a path the worker
forwards to a Durable Object that has no such route, so A-409's
`assert.equal(job.status, 404)` and its `{ error: 'Endpoint not found' }` body
are unchanged. §S6 records what A-409 does and does not still measure.

**S2d. `durable.ts` — the sweep itself.** Routed at the top of `fetch()`,
before the `/api/` surface:

```sql
SELECT id, expires_at FROM submissions
 WHERE status = 'pending'
   AND expires_at IS NOT NULL
   AND expires_at LIKE '____-__-__T%'
   AND expires_at < ?
```

then, per row, one `UPDATE ... SET status = 'expired', updated_at = ?` and one
`audit(id, 'expired', 'system@pumasi.ai', 'Pumasi Sign Engine', undefined,
{ expires_at })`. It answers `{ expired: <count> }`.

Four things about that statement, each a decision:

- **`status = 'pending'` only.** A `draft` is invisible to recipients
  (`CLAUDE.md`: *"invisible to recipients until `POST /{id}/send`"*) and
  expiring one would take a document away from a sender still writing it. The
  SPA agrees: `EnvelopeDetailView.vue:64` draws the correction pencil for
  `pending` **or** draft, and `:777` tells a draft's owner to set a new date —
  advice that stays true only if drafts do not expire.
- **`LIKE '____-__-__T%'`.** `expires_at` is TEXT and the comparison is
  lexicographic, which is exact for the ISO-8601 UTC strings the SPA sends
  (`SendView.vue:79`–`:82`: `new Date(...).toISOString()`). The
  multipart create path (`durable.ts:1032`) stores whatever a client sent
  without validating it, so the shape is pinned here: a malformed value is
  left alone rather than expired on an accidental string comparison.
- **No `LIMIT`.** A bounded sweep leaves rows unexpired with nothing saying
  so. At one shard (§S0.2) the row count is the product's entire envelope
  table and the statement is one indexed scan. If that ever stops being true,
  the fix is a bound *and* a signal, not a bound.
- **`SELECT` then `UPDATE`, not `UPDATE ... RETURNING`.** The rows are needed
  for the audit writes anyway, and this makes no assumption about which SQLite
  version workerd's Durable Object storage exposes.
- **`?` binds the current instant as an ISO-8601 UTC string**
  (`new Date().toISOString()`) — the same shape the comparison above assumes,
  said out loud because the lexicographic argument depends on it.
- **The per-row `UPDATE` re-carries `AND status = 'pending'`.** Added at spec
  review on glm's recommendation (§S9). glm looked for a reachable interleaving
  and could not construct one — workerd's input gates make the
  SELECT→UPDATE→audit sequence atomic on a single object — so this is not a
  race being closed. It is one clause that stops a future caller of
  `sweepExpired()` outside a storage-gated context from making the write a
  lie.

---

## S3 · The rest of the change

**S3a. `isTerminal` (`durable.ts:109`) gains `'expired'`**, and its doc
comment stops saying *"three"*. §S0.4 states what that changes.

**S3b. The token landing view (`durable.ts:1333`–`:1338`) gains `expired`**,
placed immediately after the `completed` test and **before** `already_signed`:

```ts
: submission.status === 'expired' ? 'expired'
: sub.status === 'signed' ? 'already_signed'
```

An expired envelope never completed, so there is no executed document to
retrieve; putting `expired` ahead of `already_signed` keeps a signer out of
`ExternalSignView.vue`'s `RETRIEVABLE` branch, which exists to hand back a
sealed PDF that in this case does not exist.

**S3c. `request-code` (`durable.ts:1350`) refuses `expired`** alongside
`cancelled` and `declined`, with the same `410`. Without this the worker
emails a verification code for a dead envelope — sending mail, which §S0.3
says this change does not do.

**S3d. `PATCH /api/submissions/{id}` honours the three settings fields**
(§S1d), and **only while the envelope is `draft` or `pending`** — the exact
pair `EnvelopeDetailView.vue:64`'s `canCorrect` draws the pencil for. On a
terminal envelope (including `expired`) the three fields are refused `409`;
`title` and `message` keep their present behaviour, which this spec does not
touch.

**The refusal is the first statement of the branch**, before the title/message
write and before any other read of the body, so a refused correction writes
nothing and audits nothing — the idiom job `0058` established for every other
guard in this file. It was **not** written that way and was moved on kimi's
code review (§S9), which found that a body carrying both a title and a settings
field got a `409` with the title write already persisted. A body with **no**
settings field is unaffected on any status.

The audit row becomes `audit(sub.id, 'corrected', …, { changed: [...] })`.
`EnvelopeDetailView.vue:608`–`:609` already renders
*"Corrected — {who} updated the {fields}"* from exactly that key and has never
received one.

**S3e. Frontend, two lines.** `SignTokenViewOut["status"]`
(`frontend/src/types.ts:217`) gains `"expired"`, and
`ExternalSignView.vue`'s `CLOSED_MESSAGES` gains its message. That map is
re-typed from `Record<string, string>` to
`Record<SignTokenViewOut["status"], string>` **so that `vue-tsc` is the test**:
a future status added to the union without a message becomes a type error
instead of a blank card. `SignView.vue:480`'s comment (§S1b) is left exactly as
written.

**And it does not become true — corrected here at spec review rather than left
standing.** glm read the comment's own scope and was right: it says *"Past-due
but not yet swept"*, which is precisely the window §S0.1 keeps. So it moves
from **always false** to **false for up to an hour**, not to true. §S1b's use
of it as evidence — the frontend names a sweep that did not exist — is
untouched by that. Like A-409's header comment (§S6) it is a comment rather
than an assertion, it is left alone rather than edited, and it rides the same
return block.

---

## S4 · Frozen acceptance cases

**New file** `service/src/test/envelope-expiry.test.ts`, cases **A-410 –
A-416**. `envelope-lifecycle.test.ts` (A-400 – A-409) is **not edited** —
see §S6.

| ID | What it drives |
| :--- | :--- |
| **A-410** | The sweep expires a past-deadline `pending` envelope: status `expired`, exactly one `expired` audit event with the system actor, `completed_at` still null, submitters untouched, and the sender's own views (`GET /api/submissions/{id}`, `?mine=sent`) report it. |
| **A-411** | The sweep leaves alone, in one run: a future deadline, a null deadline, a malformed deadline, a `draft` with a past deadline, and `completed` / `cancelled` / `declined` envelopes with past deadlines. Their statuses and audit-row counts are unchanged. |
| **A-412** | An expired envelope refuses a **token link**, end to end: `GET /api/sign/token/{t}` reports `expired`; `POST .../request-code` is `410` and writes no audit row; and `POST /api/sign/{id}/complete` through a signer session obtained **before** the sweep is `410`, with the envelope still `expired` afterwards. |
| **A-413** | `isTerminal` covers `expired`: `decline` `409`, `cancel` `409`, `send`/`remind` `409`, and none of the three writes a status change or an audit row. |
| **A-414** | The sweep is idempotent — a second run over the same store expires nothing and writes no second audit event — and its route is not on the public API surface: `POST /api/jobs/daily` and `POST /api/__internal/expire` both come back `404 {"error":"Endpoint not found"}` from the Durable Object. |
| **A-415** | `worker.ts` itself: `scheduled()` resolves the **same** `idFromName` constant the `/api/*` path resolves and POSTs the sweep to it; a non-`ok` sweep response makes `scheduled()` throw; and an inbound `GET /__internal/expire` through `fetch()` is `404` **without `SIGN_SERVICE` ever being touched**. |
| **A-416** | `PATCH` honours `expires_at`, `reminders_enabled` and `reminder_interval_days` on a `pending` envelope and audits `corrected` with the `changed` list; refuses the three on an `expired` one with `409`; and a deadline set into the future by that PATCH survives the next sweep. |

**A-415 drives `worker.ts`, which no test in this repository has ever
driven.** It imports the default export and calls `fetch`/`scheduled` against
a recording stub `Env`. That is deliberate: sub-question (2)'s whole answer is
*"both paths resolve the same constant"*, and a spec that asserts that in prose
and not in a test has asserted nothing.

### S4a · One correction to A-412 and A-413, made before the freeze

**Recorded because a correction nobody can see is the thing the freeze exists
to prevent, not because it needed permission.** The cases were authored while
the spec review ran, and on their first execution A-412 and A-413 each failed
one assertion. Both were the **same defect in the case, not in the worker**:
each obtains a signer session through the real token route, which legitimately
writes a `signer_verified` audit row (`durable.ts:1382`), and each then
asserted the envelope's audit list was literally `['expired']`. That asserted
the *setup* rather than the refusal.

Both now snapshot the audit list immediately before the refused call and assert
it is **unchanged** afterwards — which is what §S4's table says each case
drives (*"writes no audit row"*, *"none of the three writes a status change or
an audit row"*), and is a stricter test than the literal list was.

**Q-030 is not reached, on two independent grounds, and neither is a reading of
it.** First, the correction was made **while `tools/review.sh` was still
running** — glm had not returned a verdict — so CHARTER §3 requirement 2's
freeze (*"frozen when the spec review completes"*) had not taken effect and
this is ordinary pre-freeze authoring. Second, and independently: **the
standard both families reviewed is §S4's table, and it is unchanged.** glm's
own §4 states the standard it approved for A-413 as *"checks the negatives — no
status change, no audit row"*, which is exactly what the corrected assertion
makes. Nothing in either approval is stale.

**What these cases do not claim.** `support/durable-harness.ts` is
`node:sqlite`, not workerd's SQLite (`spec/0004` §S1c), so a green run here is
evidence about `durable.ts`'s logic and not about Cloudflare's storage engine.
Nothing here exercises a real cron trigger — Cloudflare firing `scheduled` on
the hour is configuration, asserted by `wrangler.jsonc` being read and not by a
test, and that limit is named in the release note (§S7).

---

## S5 · What is deliberately not built

- **No mail.** §S0.3.
- **No revival of an expired envelope.** `copy` is the route (§S0.4).
- **No expiry of drafts.** §S2d.
- **No second-accurate enforcement.** §S0.1's residual; the enforcement is the
  sweep, not a check on the signing path. Adding a per-request deadline test to
  `complete` would close the residual window and would also make frozen case
  **A-409** red on an assertion this spec has no mandate to move — see §S6.
  It is recorded as the honest next step, not taken here.
- **No `RISK_ZONES.yaml`.** `BACKLOG.md` item 7, and §S8 settles this change's
  classification without it.
- **No change to `CLAUDE.md`, `roadmap/` or `README.md`.** §S0.2 and the
  packet's ceilings.

---

## S6 · A-409, and the Q-030 reading this seat did **not** have to take

**A-409 is not amended and not edited. Every one of its assertions is still
true after this change, and it still drives the behaviour it was written for.**
Checked assertion by assertion, not assumed:

| A-409 asserts | After this change |
| :--- | :--- |
| `GET /api/submissions/{id}` → `expires_at` echoed, `status: 'pending'` | **true** — no sweep has run in that test |
| `POST .../remind` → `200`, still `pending` | **true** — same |
| `GET /api/sign/token/{t}` → `open` | **true** — the row is still `pending` |
| `POST /api/sign/{id}/complete` → `200`, envelope `completed` | **true** — the deadline alone still stops nothing |
| `POST /api/jobs/daily` → `404 {"error":"Endpoint not found"}` | **true** — §S2c |
| `count(*) WHERE status = 'expired'` → `0` | **true** — nothing in that test invokes the sweep |

This is a property of the design, not luck: **the sweep is the only writer of
`expired`, and A-409 never invokes it.** A-409 characterizes what a *deadline
by itself* does, and after this change a deadline by itself still does
nothing — the *sweep* does something. That is the residual §S0.1 names, seen
from the test side.

**So no frozen case is amended and `pumasi/DECISIONS.md` Q-030 is not
reached.** No reading of it is taken, in either direction, and this spec does
not add evidence to that entry.

**One honest debit, recorded rather than fixed.** A-409's *header comment*
says the worker has *"no `scheduled` handler and no cron trigger in
`wrangler.jsonc`"*. That sentence becomes stale. It is a comment, not an
assertion; correcting it would be a builder editing a frozen file, which is the
exact act Q-030 is open about, for no gain in what the suite measures. It is
left alone and named here — **the spec is the register, which is what CHARTER
§3 requirement 2's *"amend the spec in the open"* means** — and it is handed to
the product manager in this job's return block.

---

## S7 · Release note and window

`can_hurt` (§S8), so CHARTER §2.1 applies: a plain-language note, published,
7-day veto window in `pumasi/DECISIONS.md`. The note must carry, because a
reader who is not told will assume otherwise:

1. **What it takes away** — a lapsed envelope stops being signable.
2. **The hourly residual** — up to one hour past the deadline, the API would
   still accept a signature the app already refuses to offer.
3. **That the cron trigger itself is untested** — a `wrangler.jsonc` line, not
   an assertion (§S4).
4. **That nothing is deployed** — Q-012, Q-018 and Q-028 all bear on that, and
   the note says the merge does not reach a user.

## S8 · Risk classification

**`can_hurt`, by CHARTER Part 4's own rule rather than by anyone's judgement.**
This repository has **no `RISK_ZONES.yaml`** — re-checked at `ba1cea7` — and
Part 4 says the classification *"defaults to can hurt someone when unmapped or
unclear"*. It would be `can_hurt` on the merits too: the sweep decides that a
real person may no longer sign an agreement.

Sub-question (3) resolving to silence means **this change sends no mail**, so
the irreversible act CHARTER Part 0 never suspends is not in it.

## S9 · Review

`roadmap/STAGE.md` reads `alpha`, so CHARTER Part 0 makes the per-merge review
**advisory**, and `pumasi/tools/gate.sh` step 3 implements exactly that. It is
run anyway: `DRIVER.md` step 4 requires a code review on anything touching
personal data regardless of stage, and this decides who may sign an agreement.

**Spec review — done, before the build, both families approving.**
`pumasi/tools/review.sh --builder claude spec spec/0007 gemini glm`,
2026-09-01T01:32:02Z:

- **gemini `VERDICT: APPROVE`** — `reviews/20260831-203202-spec-gemini.md`.
  Cited `file:///home/m/dev/pumasi/governance/CHARTER.md`, **the governing
  copy**, which is what §S10 was written to make happen: on job `0058` the same
  family read the other copy on its second pass and objected on a clause that
  copy states unqualified (**Q-032**).
- **glm `VERDICT: APPROVE`** — `reviews/20260831-203202-spec-glm.md`. Three
  non-blocking notes, all three taken rather than filed: the `UPDATE` predicate
  (§S2d), the `?` binding (§S2d), and the `SignView.vue:480` comment claim
  (§S3e), which was **wrong as written and is corrected above**.

### S9a · A third defect on the PATCH route, measured here and deliberately NOT fixed

Found while building §S3d and **measured rather than read**, by driving the
built worker through the harness at `712a600`:

```
message BEFORE: {"message":"Please sign by Friday."}
PATCH {expires_at, reminders_enabled, reminder_interval_days}   -> 200
message AFTER : {"message":null,"title":"NDA","expires_at":"2026-09-02T…"}
```

**A settings-only PATCH deletes the sender's message to signers.** `title` is
preserved by `String(body.title ?? sub.title)`; `message` has no counterpart,
so a body that omits it writes `NULL`. `EnvelopeDetailView.vue:429`'s settings
dialog omits it on every save.

**It is not fixed here, and the reason is not that it is small.** Unlike §S1d,
**this change neither creates it nor worsens it**: the wipe happened on every
use of that dialog before this spec and happens exactly as often after. §S1d
qualified as a precondition because a binding deadline turns a silently
discarded field into a trap; nothing in this spec turns a silently deleted
message into anything it was not yesterday. Fixing it is a change to `title`
and `message` handling on a route this spec touches for a different reason, it
needs its own case, and `roadmap/BACKLOG.md` item 1 did not rank it. It is
handed to the product manager with the measurement above.

**One glm note is deliberately not taken, and is handed up instead.** *"Nothing
rejects a past `expires_at` on create or PATCH"* — the SPA validates it at
entry (`SendView.vue:1325`) and the worker never has. So a draft held past its
deadline and then sent expires within the hour. glm noted rather than objected,
on the ground that this is the intent's own sentence working as written and the
sender has both the correction pencil and Copy. Adding server-side validation
of a field the SPA already validates is a second change to a second route with
its own refusal semantics, and it is not what item 1 ranked. It goes in the
return block.

- ~~**Spec review** of this file, cross-family, before the build.~~ *(done,
  above.)*
**Code review — `pumasi/tools/review.sh --builder claude code ba1cea7..HEAD
kimi qwen`.** `tools/families.sh` reported **5 of 6 available** (grok
UNREACHABLE), so requirement 1's breadth rule binds and is honoured: the spec
reviewers were **gemini** and **glm**, the code reviewers are **kimi** and
**qwen**, no family is on both, and none is the builder's.

- **kimi `VERDICT: APPROVE`** — `reviews/20260831-203845-code-kimi.md`. Verified
  clause by clause that no frozen test is in the diff, and made one edge-case
  observation that **was taken after its verdict rather than filed**: the
  settings refusal was not the first statement of its branch, so a PATCH
  carrying both a title and a settings field returned `409` with the title
  write already persisted. §S3d now refuses first. **kimi's transcript
  therefore describes the diff at `712a600`, before that move**; the move is
  in the direction its own note pointed and narrows what a refusal writes to
  nothing.
- **qwen — `UNREACHABLE`, no verdict** —
  `reviews/20260831-203845-code-qwen.md`, which contains
  `curl: (28) Operation timed out after 600002 milliseconds`. **That is not an
  objection and it is not a review**: nobody of that family looked at this
  diff, and this spec does not read it as breadth it did not get. It is the
  third consecutive `pumasi-sign` job in which qwen has timed out at `curl`'s
  600 s ceiling (Q-031 records two).

**So this change carries ONE approving code-review family, not two, and the
reason is availability rather than choice.** `families.sh` reports 5 of 6, but
after removing the builder (`claude`) and both spec reviewers (`gemini`, `glm`)
the eligible pool for requirement 1's separation is exactly `{kimi, qwen,
grok}` — and `grok` is UNREACHABLE and `qwen` timed out. **`kimi` was the only
family that could both review this and keep the spec/code separation.**
CHARTER §3 requirement 3 and Part 4's can-hurt bar each ask for one approving
non-builder family and are met; the *breadth* is one, it is stated rather than
implied, and that is the notice **D-104** exists to produce.

## S10 · Which charter this spec was written against — read this first if you are reviewing it

**`pumasi/governance/CHARTER.md`**, at `pumasi` `46896b6`, which contains
**Part 0** (*"Guidance until `launched`"*, steward, 2026-08-30). That is the
copy [`pumasi-ops/roles/coder.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/coder.md)
and `pumasi-ops/DRIVER.md` name.

This is stated because **`pumasi/DECISIONS.md` Q-032 is open**: there are two
`CHARTER.md` files on this machine, they disagree about whether Part 0 exists,
they carry the identical version header, and `tools/review.sh` gives an
agentic reviewer no way to be told which governs. On job `0058` the same family
approved the spec and objected to the code within the hour because it read a
different file each time. **Nothing in this section changes a rule or resolves
Q-032**; it names the file, so that an objection citing the other copy can be
recognised as that rather than argued with.

`service/` and `frontend/` in this repository carry no copy of the charter —
checked at `ba1cea7`: `ls governance lessons` → *No such file or directory*.
