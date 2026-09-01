# SPEC 0008 — A dialog that is not about the message does not delete the message

**Intent:** [`INTENT.md`](INTENT.md) · window `pumasi/DECISIONS.md` Q-037.
**Takes:** `roadmap/BACKLOG.md` item **1** at `3edd06f`, in full, and nothing
else in that file.
**Measured at** `3edd06f`, by the coder seat of job `0073`, 2026-09-01 UTC.
`main` was `3edd06f` at the lock and did not move under this seat; every line
number below was read at that SHA and re-read after the edit.

**Governing charter — named here rather than left to a reviewer to guess.**
`pumasi/governance/CHARTER.md` at `pumasi` `2ab3a4f`, the copy containing
Part 0. Two copies of that file exist and neither says which governs
(`pumasi/DECISIONS.md` **Q-032**); spec/0007 §S10 established naming it in the
spec as this product's workaround and it worked, so it is repeated. This spec
resolves nothing about Q-032.

---

## S1 · The defect, restated as a measurement

Three lines, in two files, that sit next to each other.

**`frontend/src/views/EnvelopeDetailView.vue:428`** — `confirmSettings()`, the
*correct expiration & reminders* dialog. It sends three fields and no fourth:

```ts
await http.patch(`/submissions/${submissionId}`, {
  expires_at: expiresAt,
  reminders_enabled: settingsRemindersEnabled.value,
  reminder_interval_days: settingsReminderInterval.value,
});
settingsDialog.value = false;
ui.toast("Envelope settings updated.");
```

**`service/src/durable.ts:1310`–`:1314`** before this spec — the PATCH handler
the dialog reaches:

```ts
`UPDATE submissions SET title = ?, message = ?, updated_at = ? WHERE id = ?`,
String(body.title ?? sub.title).slice(0, 200),
body.message != null ? String(body.message).slice(0, 2000) : null,
```

`title` is kept when the body omits it. **`message` has no counterpart, so
omission is deletion.** The message is the sender's covering note to the
signers; `durable.ts:1593` returns it to every recipient on the token view.
The dialog says *"Envelope settings updated."* and closes.

**Not read — driven.** A-417 (§S4) sets a message, sends exactly the body
`confirmSettings()` sends, and asserts the note on the stored row, in the
response, and on the recipient's own `/api/sign/:id` view. Against the code as
it stood, that case is red; §S7 records both directions of that check.

**Line numbers, and one caveat about the register's.** `BACKLOG.md` item 1
cites `:1209`–`:1211` at the *deployed* commit `0e26917`. `2471a29` moved the
lines and not the substance. This spec quotes `3edd06f`, the SHA it read.

## S2 · The repair — absent means keep, present-and-null means clear

```ts
const title = String(body.title ?? sub.title).slice(0, 200);
const message = body.message !== undefined
  ? (body.message != null ? String(body.message).slice(0, 2000) : null)
  : (sub.message ?? null);
```

**Two behaviours must stay distinguishable and the shape is chosen for that,
not for brevity.**

| body | `message` written | why |
| :--- | :--- | :--- |
| no `message` key | the stored one | the settings dialog never mentions it |
| `message: null` | `NULL` | `EnvelopeDetailView.vue:380` sends exactly this when the sender empties the box (`message: message \|\| null`) |
| `message: "…"` | the string, ≤ 2000 | unchanged |
| `message: ""` | `""` | a value, not an absence; the SPA never sends one |

**`??` is the wrong operator here and the spec says so explicitly**, because
it is the shorter thing a later reader will reach for. `body.message ?? sub.message`
treats an explicit `null` as an absence and makes a message **unremovable** —
the same class of bug pointing the other way, and a capability removal
disguised as a repair. **A-418 exists to catch exactly that substitution**, and
§S7 records that it does: the `??` variant was built and run, and A-418 is the
only case that goes red.

`title` is lifted into a `const` and otherwise untouched. Its `?? sub.title`
idiom is what this change copies rather than replacing; §S3 needs the computed
value anyway.

**What this does not change**, stated so a diff reader does not have to infer
it: who may PATCH, which envelopes may be PATCHed, the 409 on a terminal
envelope (§S3), the 2000-character truncation, the response shape, and every
other field on the route.

## S3 · The audit question, answered `yes` — and the guard that must not move with it

`BACKLOG.md` item 1 declines to decide whether the `corrected` audit row
should record a message change, and the packet requires an answer in writing
either way. **The answer is yes, and `title` goes with it.**

```ts
const changed = [...settings];
if (title !== sub.title) changed.push('title');
if (message !== (sub.message ?? null)) changed.push('message');

this.audit(sub.id, 'corrected', user.email, user.name, undefined,
  changed.length > 0 ? { changed } : undefined);
```

**The reasoning, and the cost.**

- `2471a29` gave the `corrected` row a `changed` list carrying the three
  *settings* and nothing else. So the history named a reminder interval and
  said nothing about the words of the agreement. **That is the wrong way
  round**, and this spec is the one that discovered it, because it is the one
  that made an unmentioned message stop changing.
- **After §S2, a message change is always deliberate.** Before it, half of them
  were accidents and an audit row would have recorded noise. That is what
  changes the answer, and it is why answering `no` was available to earlier
  jobs and is not available to this one.
- **The one place a sender could ever discover this** is the envelope history.
  The product overwrote their note with nothing and recorded nothing; the fix
  should not leave the record silent about the deliberate case too.
- **`title` joins it rather than being left out.** Adding `message` alone would
  make the list a third idiom — one settings list, one message flag, one field
  that is never named — and `EnvelopeDetailView.vue:600` renders it as one
  sentence: *"updated the title and message"*, *"updated the expiration date
  and reminders"*. Both read.
- **Compared against the stored row, not against presence in the body.** Both
  dialogs re-send fields the sender did not touch — `:380` always sends both —
  so presence would make the history claim changes that did not happen.
  A-418 §5 pins the no-op case: a `corrected` row with no `changed` key at all,
  so the SPA falls back to *"Corrected by X"* (`:610`).

**The debit, named rather than buried.** The `corrected` row starts carrying a
`changed` list on the correct-details path, where before it carried none. That
is a widening of what a past-facing record says, it is strictly more
informative, and it is in the intent and in the release note.

**The 409 guard stays keyed on `settings`, not on `changed`.** spec/0007 §S3d
promised in terms that *"a body with no settings field is unaffected: title and
message keep the behaviour they had, on every status"*. Widening the audit list
must not quietly widen the refusal with it, and **A-419 asserts both halves**:
a title-and-message correction on a `completed` envelope still succeeds, and a
settings field on the same envelope is still refused with `409` and still
writes nothing.

## S4 · The frozen cases

New file `service/src/test/envelope-correction.test.ts`, run by the same
`.github/scripts/run-service-suite.sh` as every other case in this repository.
**No second runner is stood up**, and the guard
`.github/scripts/assert-service-suite-ran.sh` counts it like the rest.

| Case | What it pins in place |
| :--- | :--- |
| **A-417** | A settings-only PATCH — literally the body `confirmSettings()` sends — leaves the message on the stored row, in the response, and on the recipient's `/api/sign/:id` view; the settings themselves still land; the history names the three settings and claims no title or message change. |
| **A-418** | `message: null` still clears it, a string still sets it, `""` is a value, 2000-character truncation is unchanged, and a no-op correction whose body **carries both keys at their stored values** — the shape `EnvelopeDetailView.vue:380` sends on a save with no edit — writes no `changed` key. |
| **A-419** | Title and message are both named in the history; a truncated title counts as a change; a body carrying a settings field **and** content on a live envelope lands both and names both; a title-and-message correction on a terminal envelope still succeeds; a settings field on it is still refused `409` and still writes nothing. |

**Three of those clauses are there because glm's spec review
(`reviews/20260831-214423-spec-glm.md`) asked for them, and all three were
taken into the build rather than filed.** §2 of that review noted that A-418's
no-op case discriminates a comparison-keyed audit list from a presence-keyed
one **only if the body carries the keys**, which is the L-006 failure mode
exactly; the body shape is now pinned in the case and named in the row above.
The same section noted that no case drove a body carrying settings and content
together; it now does. The third — a legacy row with a title over 200
characters re-truncating and being *named* as a change — is unreachable,
because every write path on the route truncates, and it is recorded here rather
than defended against.

**Why a new file rather than an addition to `envelope-expiry.test.ts`.** That
file holds A-410 – A-416 and is frozen under spec/0007. Its **A-416** already
asserts `out.title === 'Mutual NDA'` after a settings-only PATCH — *"PATCH
without a title blanked the title"* — which is precisely the property this spec
generalises to the message. **A-416 is untouched and still passes** (§S6), so
`pumasi/DECISIONS.md` **Q-030** — may a builder amend a frozen case — is not
reached and no reading of it is taken.

The file re-states the harness helpers rather than importing them from a
sibling, which is the reason the sibling itself gives: a frozen case that
breaks because a neighbouring frozen case's fixture moved measures the wrong
thing. `pumasi/lessons/L-007` cuts the other way for rules; these are fixtures.

## S5 · What is deliberately not built

- **The settings dialog is not widened to send `message`.** `BACKLOG.md` item 1
  refuses to authorise it in its own text and the packet repeats the refusal.
  It is a different change with a UI cost. Not proposed here either; the
  handover says why it is not obviously right.
- **No recovery of messages already deleted.** They were overwritten with
  `NULL` and there is no shadow copy. The intent says so in the sender's own
  words rather than implying a repair reaches backwards.
- **No server-side rejection of a past `expires_at`.** Still open, still handed
  up, unchanged from spec/0007 §S9a's handover.
- **No deploy, and no seat here proposes a deployer.** §S8.

## S6 · Every frozen case that already existed, checked rather than assumed

`A-416` is the only prior case that drives this route. Assertion by assertion,
against its body `{expires_at, reminders_enabled, reminder_interval_days}` on
an envelope seeded with `message = null`:

| A-416 asserts | after this spec |
| :--- | :--- |
| `200`, `expires_at`, `reminders_enabled`, `reminder_interval_days` | unchanged — §S2 touches neither branch |
| `out.title === 'Mutual NDA'` | unchanged — `title`'s idiom is copied, not replaced |
| `changed` sorts to `['expiration date','reminder interval','reminders']` | **unchanged, and this is the load-bearing one.** Title is absent from the body, so `title === sub.title` and nothing is pushed. Message is absent, so `message === (sub.message ?? null)` — `null === null` — and nothing is pushed. |
| the sweep, and the terminal 409 | untouched |

Measured, not reasoned: the full suite is green at 31 with A-416 among them
(§S7). `A-104` and `A-207`, which pin the CI guard and its two callers, are
unaffected — no script and no workflow changes.

## S7 · Verification, in both directions

**Root `npm test` at `3edd06f`, before the change, run twice, identical:**
`Test Files 6 passed (6)`, `Tests 85 passed (85)`, `# pass 28`, `# fail 0`,
`assert-service-suite-ran: 28 passing, 0 failing, from 5 compiled`.

**After: `# pass 31`, `# fail 0`, `31 passing, 0 failing, from 6 compiled`.**
Three cases, one new compiled file. The frontend half is untouched and stays at
`Tests 85 passed (85)`.

**A green count is only evidence if red was available**, so both mistakes were
built and run rather than argued about:

| Variant built | What was substituted | Result |
| :--- | :--- | :--- |
| the defect, restored | **§S2's `message` const alone**, back to `body.message != null ? String(…).slice(0, 2000) : null`. §S3's audit widening left **in**. | **A-417 and A-419 fail**, `# pass 29 # fail 2` |
| the `??` over-correction | the same const, to `body.message != null ? String(…).slice(0, 2000) : (sub.message ?? null)` | **A-418 fails**, `# pass 30 # fail 1` |
| §S3 alone reverted | the two `changed.push` lines removed; §S2's `message` const left **in** | **A-418 and A-419 fail**, `# pass 29 # fail 2` |
| the repair as written | — | `# pass 31 # fail 0` |

**The middle column is spelled out because glm's spec review read the first row
two ways and could not tell which was run.** It was the narrow one: one
expression, audit widening intact. glm reasoned that A-419 would then stay
green and the count should be `# fail 1`; that reasoning misses A-419's
**title-only** PATCH, `patch({ title: 'Mutual NDA (rev 3)' })`, whose body
omits `message` — so the restored defect nulls a message the case then asserts
is still there, and the audit list it asserts as `['title']` arrives as
`['message', 'title']`. `# fail 2` is what was measured, and it is measured
from the narrow substitution. The row was under-described; the reading was not
wrong.

That mutation table is the whole reason A-418 is in this spec: without it, the
cheapest wrong fix is green.

## S8 · What this does not reach, and it is the thing that matters most

**`sign.pumasi.ai` will keep deleting senders' messages after this merges.**

The live worker is built from `0e26917` — established by job `0071` by chunk
fingerprint and by `wrangler versions view` reporting `Handlers: fetch` with no
`scheduled`. `2471a29`, `3edd06f` and this change are all undeployed. The
defect is present in both trees, so the gap did not block the repair; it also
is not closed by it.

**No seat on this job deployed, proposed a deployer, or set a date.**
`pumasi/DECISIONS.md` **Q-012** — who may deploy a merged build — is open and
explicitly outside CHARTER Part 0's proceed-on-default rule. **Q-028** records
that earlier repairs already wait in the same undeployed bundle; this is the
fourth. It is named in the release note, in the handover as somebody's next
packet, and here.

And the standing rider: **a green suite here is not evidence about
production** — Q-018's default part (c). This suite runs node:sqlite, not
workerd's SQLite (spec/0004 §S1c), and it runs a build nobody is served.

## S9 · Risk class — `can_hurt`, by the rule and not by the reading

`pumasi-sign` has **no `RISK_ZONES.yaml`** — re-checked at `3edd06f`,
`ls RISK_ZONES.yaml` → *No such file or directory*, and it is this repository's
`BACKLOG.md` item 5. CHARTER Part 4: the classification *"defaults to can hurt
someone when unmapped or unclear"*. **So this is `can_hurt`, and the window is
opened rather than argued down.**

`BACKLOG.md` item 1's author records the other reading — *"not `can_hurt` on
this seat's reading, it repairs a destructive write rather than creating
one"* — and then says to plan for the window anyway. This spec agrees with the
reading and takes the window, and it does not treat the reading as a reason to
skip it: reclassification is itself a can-hurt change (Part 4) and no seat here
is making one.

**On the merits there is also something to point at**, which is why the
disagreement is cheap: the route handles a sender's own text about an agreement
— personal data on the handling path — and §S3 changes what a past-facing audit
record says about a correction. Neither is why the class is what it is, but
neither is nothing.

Release note and the 7-day window: `pumasi/DECISIONS.md` **Q-037**, filed in
the shape **Q-035** established for this product — both windows in one entry,
the longer one governing.

## S10 · Review

CHARTER §3, and `roadmap/STAGE.md` is `alpha`, so Part 0 makes review
**advisory** rather than blocking — it is run in full regardless, and its
transcripts are committed including any that object.

`pumasi/tools/families.sh` at this job: **5 of 6 available**, `grok`
UNREACHABLE. So requirement 1's breadth rule binds and is honoured the way
Q-035 honoured it: **the spec reviewer and the code reviewer share no family,
and neither is the builder** (`claude`). Recruitment order is the packet's —
Claude → Gemini → Grok → Qwen → GLM → Kimi — with the builder and the
unreachable family skipped in place.
