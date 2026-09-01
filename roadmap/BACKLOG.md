# BACKLOG — what gets built next, in order

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 5).
First pass 2026-08-30, steward-directed: *"introduce very similar UI and UX
[to the incumbent] in pumasi sign — let these items in the queue."*
**Reordered 2026-09-01 (fifth reorder)** after the product evaluation that
re-measured this file against `main` @ `56a8bf8`; the reasoning is in that
commit's message, and the steward vetoes by reverting.

One list, features and bugs together, because a priority that cannot compare
them is not a priority. Every entry points at its source and carries one line
of why-here. **The top of this file is what the project manager's next coder
packet builds.**

## Why this reorder exists

**Item 1 was delivered, and the sentence it argued from was disproved by the
delivery.** Both halves matter and the second is the one a register learns
from.

### The delivery, verified here rather than read off the decision entry

Coder job `0058` merged `68e5d08` and `56a8bf8`. Re-read in
`service/src/durable.ts` at `56a8bf8` by this evaluation:

| Route | Guard | Line **now** | Line the entry cites |
| :--- | :--- | :--- | :--- |
| `cancel` | `if (isTerminal(sub.status)) return json({ error: 'This envelope is already closed' }, 409)` | **`:1252`** | `:1239` |
| `complete` | `if (isTerminal(submission.status))` → `410` | **`:1452`** | `:1434` |
| `decline` | `isTerminal` → `409`, then `me.status === 'signed'` → `409`, then `!submitterTurn(me)` → `409` | **`:1513`** | `:1490` |

One predicate, `isTerminal`, at `:109`. In all three routes the guard is the
**first statement of the branch**, before the request body is read, so a
refusing path writes nothing and audits nothing. **The line numbers in
`pumasi/DECISIONS.md` Q-031 are the pre-fix ones**; they are correct as a
record of the defect and will not locate the repair. That is recorded rather
than corrected in place — Q-031's text is not this seat's to edit.

### The sentence this file got wrong

Item 1 argued, in this file's own words:

> So the omission mostly produces the **wrong refusal** — *"Already signed"*
> (409) where the other terminal states give *"no longer active"* (410) —
> rather than a wrong write.

**That was false, and the work it ranked is what disproved it.** The reasoning
behind it was that `if (me.status === 'signed')` catches the reachable cases,
because an envelope only completes once every non-CC signer is `signed`.
**The quantifier was the error.** `durable.ts`'s completion count reads
`AND is_cc = 0`, so a **CC recipient's** status is still `pending` when the
envelope completes. That recipient passes both guards, reaches `finalize()` a
second time, writes a **second** `completed` audit event, and where a PDF is
present re-stamps the executed document. A reachable wrong write, not a wrong
refusal code.

**Where the measurement lives:** `spec/0006/SPEC.md` **§S1a** states the
correction and names this file as the register that had it wrong; frozen case
**A-406** in `service/src/test/envelope-lifecycle.test.ts` is the measurement —
it asserted the second completion event and the count was `2`. `spec/0005`
§S6.4 had it right before this file did. The builder did not edit this entry,
correctly, and handed the correction up in its return block; it is taken here.

**What is *not* claimed, because the delivery was careful about this and so is
this file.** [`VALUE.md`](VALUE.md) **C1** is **not** falsified: the stamped
PDF and its audit certificate live in R2 and a status overwrite does not touch
them. What was damaged is narrower and still real — the Durable Object row and
the audit log came to say `cancelled` about an envelope whose certificate says
`completed`. One product, two records, one claim: **L-009** at row scale.

### Re-measured before re-ranked, with the number of runs behind each figure

Per [`STAGE.md`](STAGE.md) §0 rider (a), run by this seat at `56a8bf8` on
2026-09-01, not inherited and not copied from the packet:

```
$ npm test          # = pumasi/tools/gate.sh step 1, repository root
Test Files  6 passed (6)          # 2 runs read
     Tests  85 passed (85)        # 2 runs read
# pass 21                         # 4 runs
# fail 0                          # 4 runs
assert-service-suite-ran: 21 passing, 0 failing, from 4 compiled   # 3 runs
```

**Runs behind each figure, stated because "I ran it" without a count is what
rider (b) exists to stop.** Root `npm test` was run **three** times and
`service/`'s own `npm test` once, so the service assertion count rests on
**four** runs and the guard line on **three**. The frontend figures rest on
**two** runs read: a third root run produced them but its output was truncated
before capture, and a figure nobody read is not a run. All identical; no
determinism claim is made from four runs and none is needed here.

**The number did not move, and that is the point.** 21 across four files, the
same as the fourth evaluation measured at `f7c8d03` and the same as job `0058`
measured either side of its own repair. **The release closed a defect and
widened no coverage.** A defect closed is not breadth gained, and this reorder
does not treat it as any.

### What moved

- **Old item 1 → Retired**, with the struck sentence recorded rather than
  deleted.
- **Old items 2–7 → 1–6**, unchanged in substance except where re-verification
  changed a fact. Old item 2 (`expires_at`) is the new **item 1** and its text
  now says what it is blocked on, which is not what the last reorder implied.
- **New item 7 — `RISK_ZONES.yaml`**, which this repository does not have.
  Ranked seventh, and the reasoning is in the entry because the packet asked
  for it there rather than in a commit message.
- **Old items 8–18 keep their numbers.** The parity mandate still resumes at
  item 8.

### Re-verification, and what is labelled rather than claimed

`0058` touched `service/src/durable.ts` and `spec/`, so every entry citing a
line number in either was suspect. **Re-read in the tree at `56a8bf8` by this
evaluation:** item 1's `grep` for `scheduled|triggers|crons` (still no
matches), item 2's `e2e-workflow.test.ts` imports (still four, still no route,
no worker, no store), item 3's `#6`/`#10`/`#11` surfaces, item 4's
`FeedbackDialog.vue` capture, item 5's three `package.json` files, item 6's
router table. **Re-measured against the live host** at 2026-09-01 00:29 UTC:
the deployed bundle is still `/assets/index-j38Qwibz.js` and
`GET /api/auth/login?next=%2F` is still `404`, so **B1 and B2 are confirmed,
not carried.** Everything else in items 8–18 is *carried, not confirmed* —
those entries cite a design spec, not this tree.

**`PRODUCT-RULES.md`, read fresh this packet and reported rather than assumed.**
Still **not on `pumasi` main** — checked at `pumasi` @ `3bc1822`:
`ls PRODUCT-RULES.md` → *No such file or directory*, and it exists on one
commit, `0115758`, on the unmerged branch `worktree-product-rules`. That is
**Q-017**, open, now flagged by **seven** consecutive evaluations, and
**absence from main is not compliance**. Read from that branch this pass: v1.0,
PR-1 (version numbers, binds always) and PR-2 (in-app feedback, binds at
`beta`) unchanged from the last reading. Both gaps stay ranked, now at items 5
and 4 respectively.

---

## The order

**1 · Make `expires_at` do what the UI already tells the user it does** —
source: coder job `0050`'s proposal 3 and frozen case **A-409**; `CLAUDE.md:107`–`:110`.

**The gap, re-measured at `56a8bf8` by this evaluation and unchanged.** `CLAUDE.md` names `expired` as one of six
submission statuses, *"past its optional `expires_at` deadline — flipped by the
daily job"*. There is no daily job on the worker:

```
$ grep -n 'scheduled\|triggers\|crons' service/src/worker.ts service/wrangler.jsonc
(no matches)
```

No `scheduled` export, no cron trigger. A-409 drives it end to end: the worker
**never writes `expired`**, a past deadline transitions nothing, and the
envelope stays signable forever.

**Why this is a broken promise and not merely undocumented behaviour — this is
the part that decides the recommendation.** The product does not quietly ignore
a field nobody sees. It **asks the user for the deadline, validates it, shows
it back, and states in words what it means**:

- `SendView.vue:865` and `:901` send `expires_at` from the Send wizard;
  `EnvelopeDetailView.vue:429` sets it from *"correct expiration & reminders"*.
- `SendView.vue:1329` and `EnvelopeDetailView.vue:1098` refuse a date in the
  past — *"The expiration date must be in the future."*
- `EnvelopeDetailView.vue:746` displays *"· expires {date}"*.
- And the sentence this entry turns on, in **both** places
  (`SendView.vue:1336`, `EnvelopeDetailView.vue:1104`): **"Without an
  expiration date, the envelope stays open until completed or voided."** The
  plain reading — the only reading — is that *with* one, it does not.
- `EnvelopeDetailView.vue:60`–`:61` even computes `stuck` client-side from
  `expires_at`, and `:777` tells the sender *"Its expiration date has already
  passed — set a new one"*.

So the **sender's** screen behaves as if the deadline is enforced, while a
**recipient** holding a token link can still sign it. That asymmetry is the
user-visible harm, and it is why this outranks breadth-of-coverage work.

**Which of the two corrections this seat recommends: the scheduled handler.
Neither was made here — `CLAUDE.md` and `service/` are both outside this
role's `May Write`.**

- **Recommended — (A) add a `scheduled` handler and a cron trigger** that flips
  past-deadline `pending` envelopes to `expired`. It is new infrastructure and
  not a one-liner: a `crons` entry in `wrangler.jsonc`, a `scheduled` export in
  `worker.ts`, a Durable Object entrypoint that does the sweep, an audit event,
  and a decision about whether an expired envelope notifies anyone. `backend/`
  has the shape already (`POST /api/jobs/daily`) and may be read for
  precedent — but **not** treated as the answer, since Q-018 is open.
- **Not recommended — (B) declare `expires_at` advisory on the worker.** The
  packet describes this as a `CLAUDE.md` edit that narrows a promise. Measured,
  it is **larger than a documentation edit**, and that is the finding: the
  promise is not in `CLAUDE.md`, it is in two strings the SPA shows users
  (`SendView.vue:1336`, `EnvelopeDetailView.vue:1104`). Being honest under (B)
  means changing that copy, and arguably removing the date picker and the
  future-date validation that make the field look enforced. That is a
  user-visible capability removal on the served tree.

**And that is what would make (B) `escalated`, not this entry.** Option (A)
makes the code do what the product already says; no promise moves, so it is
ordinary work and is ranked here. Option (B) retracts a promise the product has
already made to senders in words — a change to what the product promises, which
this role's duty 1 defines as escalation ground. **This seat is not raising a
`DECISIONS.md` question, because it is not recommending (B).** If the steward
or a later evaluation prefers (B), it needs one first, with the UI-copy cost
above named in it rather than discovered afterwards.

**Why here, and what it is and is not blocked on — stated in this entry rather
than left for a packet to discover.** Every sender who sets a deadline is
affected, and no direct API call is required, unlike the transition repair that
was item 1. With that repair delivered at `68e5d08`, this is the highest-ranked
**build** entry in the file.

**It is not blocked on a steward decision.** The product choice this entry
turns on — **(A)** the scheduled handler over **(B)** withdrawing the promise —
was made by the fourth reorder, is unvetoed, and stands. No `DECISIONS.md`
window gates it: unlike **B1** and **B2** below, nothing here waits on Q-012 or
Q-021. A coder packet may take it today.

**It is blocked on design, in the ordinary sense that it adds infrastructure
that does not exist**, and that is why the packet taking it runs the full
charter flow — intent → spec + frozen tests → build — rather than a patch. Four
things have to be decided *in the spec*, by the builder, with named defaults,
and none of them is a steward act:

1. **The cron cadence.** `backend/`'s precedent is daily at 09:00 UTC; nothing
   requires the worker to match it, and Q-018 means that tree may be read for
   shape but not treated as the answer.
2. **The sweep's entrypoint.** A `scheduled` export in `worker.ts` has to reach
   a Durable Object, and every envelope lives in one — how the sweep enumerates
   them is the real work in this item and there is no existing pattern in
   `service/` to copy.
3. **Whether an expiry notifies anyone.** The SPA promises the envelope stops
   being signable; it promises nobody an email. Silence is the smaller
   commitment and is the honest default.
4. **The audit event.** `expired` is a status the audit log has never carried;
   it needs a name, and the same `isTerminal` question as item 1's repair — an
   expired envelope should refuse the same transitions a completed one does.

**And it is `can_hurt` under CHARTER Part 4**, which a packet should plan for
rather than discover at the gate: the sweep decides that a real person may no
longer sign an agreement, and if (3) resolves toward notifying, it sends mail on
a sender's behalf. **This repository has no `RISK_ZONES.yaml`** (item 7), so
Part 4's own rule applies — *unmapped or unclear defaults to `can_hurt`* — and
the classification is settled by that default without anyone reasoning it out.
That is the whole reason item 7 ranks where it does; see its entry.


**2 · Test the deployed tree beyond its stamper — the breadth that is left**
— source: coder job `0032`'s `SUGGESTED_NEXT_TASKS` (`priority: high`),
`pumasi/DECISIONS.md` **Q-018** and **Q-025**, [`STAGE.md`](STAGE.md) §2.1,
`CLAUDE.md` (*"test coverage here is thin and you should know it before you
trust it"*). **Was item 3, and item 1 before that. Not retired, and demoted
on delivery rather than silently — it has now been passed twice by defects its
own coverage found.**

**What its three named slices delivered, verified in the tree this pass.** The
entry proposed, in order: `establishSession`'s account rule, then session
validation, then envelope state transitions. **All three are in.**
`auth-session.test.ts` (A-300–A-308) constructs the real Durable Object —
*"whole schema, migrations, routing"* (A-300) — through
`test/support/durable-harness.ts`, and covers the Q-018 divergence as
**A-302**, *"establishSession admits a verified email at any domain — recorded,
not endorsed"*. That is the entry's own boundary honoured exactly:
**characterize, do not adjudicate.** `envelope-lifecycle.test.ts` (A-400–A-409)
covers the transitions and is what found the two defects that became items 1
and 2 of the fourth reorder — the first of which is delivered and retired below,
the second of which is now this file's item 1.

**So the two sharpest sentences this entry used to carry are now false and are
withdrawn**, rather than left to read as pending:

- ~~"both assertions are against one file"~~ — four files now; two of them
  drive routes against a real Durable Object.
- ~~"`durable.ts` … covered by nothing"~~ — sessions and the envelope surface
  are covered.

**One sentence survives verbatim, re-checked in the tree at `56a8bf8` by this
evaluation:**
`e2e-workflow.test.ts` **is still not an end-to-end test of anything.** Its
imports are `node:test`, `node:assert/strict`, `pdf-lib` and
`stampAndCertifyPdf` — identical to `stamping.test.ts` — and it calls no route,
starts no worker and touches no store. The file *name* over-states what it
does, and `# pass 21` in a release note will be over-read exactly as `# pass 2`
was. Renaming it is a five-minute honesty fix and belongs in whichever packet
takes this item.

**What is left, and a packet should say which strand it takes.**

- **Named first slice — the OAuth callback, which is where job `0050`'s
  proposal 5 lives.** Verified by the fourth evaluation at `service/src/durable.ts:766`; `0058` moved
lines in this file, so the number is **carried, not confirmed** — the guard
itself was re-read and is unchanged:
  the guard is `claims.email_verified === false`, so an `id_token` that
  **omits** the claim passes. Stated at the strength the evidence supports and
  no higher: this is on an **uncovered branch**, proposed from source with no
  test exercising it, and the code takes the token directly from the provider's
  token endpoint over TLS (the comment at `:757`–`:758` says so), which is real
  mitigation. It is *security-shaped on a live auth path*, not a demonstrated
  vulnerability, and this seat is **not** asserting it is exploitable. That is
  precisely why it ranks as the first slice here rather than as its own
  `priority: high` entry: **the cheap next step is the covering test**, which
  is what job `0050` suggested as a `priority: medium` packet (the OAuth
  branch, token endpoint stubbed). If the test shows a real admission path, it
  is promoted out of this entry on that evidence.
- Covered by nothing, re-checked: `worker.ts`, `storage/r2.ts`, `mail.ts`,
  `feedback.ts`, `convert/graph.ts`; and inside `durable.ts` — envelope
  creation, correction and copy, templates, admin, every file route, and
  `finalize`'s stamping branch.
- **The integration suite still drives the wrong tree.**
  `frontend/playwright.config.ts:63` boots `uvicorn app.main:app` locally, or a
  container from the root `Dockerfile` in CI — `backend/`, both times.
  Unchanged, and now the single largest thing in this entry.

**Boundary, unchanged and it must survive:** *characterize, do not adjudicate.*
A test that records what the worker does is ordinary work; a test written to
assert the worker's account rule is the *correct* one answers **Q-018**, which
is the steward's. A-302 is the model.


**Why here, and it is second rather than third only because the entry above it
was delivered.** It gained no ground at `68e5d08`: that release **widened no
coverage** — the gate prints the same 21 assertions it printed before, from the
same four files — so nothing in this entry closed. Breadth still ranks below
the one remaining defect on the served tree (item 1), and above everything no
user has reported.

**3 · Three small presentation defects, one packet — #6, #10 and #11** —
source: issues [#6](https://github.com/pumasi-ai/pumasi-sign/issues/6),
[#10](https://github.com/pumasi-ai/pumasi-sign/issues/10) and
[#11](https://github.com/pumasi-ai/pumasi-sign/issues/11) — all three
`accepted`, all three `priority: normal`; #10 and #11 triaged by the fourth
evaluation, #6 by the one before it. **Labels re-read on the tracker by this
evaluation** — all three still `accepted` · `priority: normal`, all three still
open, so the intake verdicts stand and nothing is re-triaged here. **Was item 4.**

**Why one entry.** Three separate users reported three defects that are all
small, all presentational, and two of which are visible in the same committed
screenshot. Splitting them costs three packets and three review cycles for what
is one afternoon in `frontend/`.

- **#6 — inert `gap-*` classes on three views.** Re-measured at `56a8bf8` and unchanged: this frontend has no Tailwind — Vuetify `^3.13.0` only, whose
  utility is `ga-*`. `.ga-2` is in `vuetify.css` and `.gap-2` is not.
  `BrandingView.vue:113`, `:128`, `:142` (the reported surface);
  `LoginView.vue:119`; and `LandingView.vue` (`:41`, `:48`, `:53`, `:90`),
  which *do* render because that file defines `.gap-2/3/4` in its own
  `<style scoped>` (`:260`–`:262`) — leave or converge, the coder's call.
- **#10 — the app-bar wordmark is clipped on a narrow viewport.** Reported from
  the live product at 384x691. **The logo mark is fine; the text is cut** —
  `App.vue:33` renders `{{ branding.companyName || 'Pumasi Sign' }}` beside the
  `<img>` inside one `v-app-bar-title`, and at 384px the always-present
  `FeedbackDialog` button crowds it to **"Pumasi Si"**. This is **global
  chrome, not the login page**: every view has this bar, and signed in it is
  tighter still (`Send`, `Templates`, `Branding`, `Logout` in the same row).
- **#11 — the provider marks are monochrome MDI glyphs, not brand marks.**
  `LoginView.vue:120` and `:123` use `prepend-icon="mdi-google"` and
  `prepend-icon="mdi-microsoft"`. The reporter's named comparison was checked
  rather than reasoned about: `pumasi-booking` @ `f6faa85` `service/src/pages.ts:1505`
  and `:1507` hold inline brand-coloured SVGs — Google's four paths, Microsoft's
  four squares — behind the same two labels. Match that **behaviour**; if code
  is copied, `COPIED.md` records it.

**Two limits on this entry, and they are the packet's, not suggestions.**
**(i) No visual design is promised here.** If any of the three wants a
responsive lockup, a short-form mark, or a provider-logo policy rather than a
CSS repair, that is the **Graphics Designer's** through the project manager —
this seat ranks the defects and does not draw the remedy. **(ii) On #11, this
seat did not read Google's or Microsoft's brand guidelines and asserts nothing
about what they require.** The ranking rests on the in-project comparison
alone. Whoever implements should check both providers' published guidelines
before choosing between redrawn marks and official assets, and bring back
anything that constrains the fix.

**Why here.** Below two live defects on the served tree and below the coverage
that would catch the next one; above everything that no user has reported.
Note that the last reorder ranked #6 partly on riding along with the #7 fix,
and that ride was spent at `d18d534` — it stays high on its own size and on
having acquired two companions, not on a shared deploy.


**4 · The feedback screenshot must be attached, not pre-attached** — source:
`PRODUCT-RULES.md` **PR-2** (v1.0, read fresh this packet from `pumasi` branch
`worktree-product-rules` `0115758`; **still not on `pumasi` main** — checked at
`pumasi` @ `3bc1822`; that is **Q-017**, now flagged by **seven** consecutive
evaluations, and absence from main is not compliance), CHARTER §5.2.
Re-read in the tree at `56a8bf8` by this evaluation and **unchanged**: opening the dialog sets a fallback
canvas as the attachment immediately (`FeedbackDialog.vue:185`–`:189`,
`screenshotIsAuto.value = true`) and then replaces it asynchronously with a
real `html2canvas(document.body)` capture (`:193`–`:197`). The user presses
nothing. PR-2 says *"a screenshot travels only when the user attaches one"*.
The user sees it and can remove it (`removeScreenshot`, `:201`), so today this
is opt-out and informed — but in an e-signature product the page being captured
is somebody's contract, and §5.2 says *never the user's own material*. Make it
a button the user presses. Why here: PR-2 binds at the `beta` promotion, this is
the only clause it fails, and it is cheaper to fix now than to hold a promotion
for. **This is the deployed behaviour, not a branch one** — the feedback widget
that produced issues #4–#9 is the one live on `sign.pumasi.ai`.


**5 · One version number, and put it in the reports** — source:
`PRODUCT-RULES.md` **PR-1**, which binds *always, from the first commit*, and
is not met. Re-measured at `56a8bf8` by this evaluation and unchanged: the root `package.json` carries **no
`version` field**; `frontend/package.json` reads `0.0.0` and
`service/package.json` reads `0.1.0` (two hand-maintained copies — L-007); no
version is visible to a user anywhere in the SPA; there is no `/version`
endpoint; and `FeedbackDialog.vue::buildContext` (`:105`–`:121`) sends
**thirteen** fields — page, URL, user, browser, platform, language, timezone,
viewport, screen, network, time, cores, device memory — and not the version.
Why here: all **seven** open issues are defect reports without a version, which is a
request to guess, and the fix is one source of truth plus two readers.

**The cost of this entry went up at `d18d534`, and the note that it "rides
naturally with item 2" is now wrong and is removed.** The root `package.json`
was edited by that commit and its `version` field was **deliberately** left
absent — `spec/0003` froze acceptance case **A-208**, which asserts the absence
precisely so that "a later packet cannot take it in passing"
(`spec/0003/SPEC.md:211`, `:251`). So the packet that takes this item must also
retire or amend A-208 in the same commit, and should say so in its intent.
That is a small, stated cost, not a blocker.


**6 · A settings shell, with branding inside it** — source: issue
[#5](https://github.com/pumasi-ai/pumasi-sign/issues/5) (`accepted`,
`priority: normal`); pulled out of item 17 (spec §8), which keeps the rest.
There is no `settings` route and `/branding` is top-level — re-read at
`56a8bf8`, where the route table has moved to `router/routes.ts:69`–`:70`
(`path: "/branding"`, `name: "branding"`) and the last reorder's
`router/index.ts:70` no longer locates it. Ship the shell and move branding under
it; the account defaults, notification preferences and retention controls that
fill it stay in item 17. Why here: it is the container every later
settings-shaped item needs, and shipping it early stops each of them inventing
its own home.


**7 · Classify this repository's paths — the `RISK_ZONES.yaml` that does not
exist** — source: `pumasi/DECISIONS.md` **Q-031**'s own *Risk class* row, which
reports the absence, and CHARTER **Part 4**. **New in this reorder.** It is a
build; this seat ranks it and does not write it.

**The gap, measured rather than reported.** `ls RISK_ZONES.yaml` in this
repository → *No such file or directory*, confirmed by this evaluation at
`56a8bf8`. CHARTER Part 4 says the classification *"lives in `RISK_ZONES.yaml`
in each repository, is one boolean per path, and defaults to **can hurt
someone** when unmapped or unclear."*

**The cost of the absence is on the record and is exactly one paragraph.** Job
`0058` had to apply Part 4's table by hand to classify Q-031, and said so
inside the decision entry rather than hiding it: *"`pumasi-sign` carries no
`RISK_ZONES.yaml` (checked, not assumed), so CHARTER Part 4's table was applied
directly."* It reached the right answer — `can_hurt` — and the reasoning is
auditable. The next such release repeats the work, and the release after that
may reason to a different answer, which is the actual risk here.

**Why it ranks seventh and not higher — the packet asked for this reasoning
here, so here it is.**

1. **The charter's default already fails safe, and that is decisive.** An
   absent file cannot cause *under*-classification: *unmapped or unclear
   defaults to can hurt someone*, and Part 4 adds that *"guessing wrong in the
   safe direction costs one extra review."* So the whole harm this file
   prevents is an over-classification tax and an inconsistency between two
   seats' hand-reasoning. Every entry above it addresses something that is
   wrong in a direction the system does **not** correct on its own.
2. **It serves no user.** Items 1 and 2 are a broken promise and the coverage
   that would catch the next one; item 3 is three defects three people
   reported; items 4 and 5 are `PRODUCT-RULES.md` clauses that bind. This is
   process infrastructure. It is worth doing and it is not worth doing first.
3. **It is small, which cuts both ways.** Half an hour of work is a weak reason
   to rank something high and a good reason not to leave it undone before a
   long feature run — which is why it sits immediately above item 8, where the
   parity mandate resumes and several entries will be `can_hurt`.

**The precedent is not what it was described as, and a packet should know
before copying it.** The report that prompted this entry says `pumasi-booking`
has a `RISK_ZONES.yaml`. Read directly at `pumasi-booking` @ `2453adc`, it has
**two** — `core/spec/RISK_ZONES.yaml` and `service/spec/0002/RISK_ZONES.yaml` —
and **neither is at the repository root Part 4 names**. Both are scoped to a
spec item. No other repository in the fleet has one at all (`pumasi`,
`pumasi-web`, `pumasi-ops` and `pumasi-tunnel` checked, none tracked). So
*"the classification lives in `RISK_ZONES.yaml` in each repository"* is
currently true of no repository.

**This entry does not raise a `DECISIONS.md` question about that**, because it
does not need one: Part 4's words name the repository root, and booking's
nesting is a deviation rather than an authority. **Put the file at the root.**
Record the divergence from booking in the commit rather than silently matching
either shape.

**What the file should say, and why it is nearly a one-liner.** Booking's
service-level file is the useful precedent for its *content*: `can_hurt: "*"`
with a stated reason, on the grounds that the service holds third parties'
personal data and acts on their behalf. `service/` here is the same shape and
stronger — it holds signers' names, email addresses, IP addresses, user agents,
signature images and the documents they signed, it sends mail on a sender's
behalf, and it writes the audit record of a legal act. Enumerating exceptions
inside it would be looking for loopholes in our own risk model. `backend/` is
the harder call and **the packet must not answer Q-018 by classifying it** —
recording that it serves no user is a fact; concluding it therefore does not
matter is the steward's.

**8 · Focus-mode shells for prepare / tag / sign** — source: spec §1
(shell 2). Full-screen wizard and signing surfaces: global chrome hidden,
minimal header with close-X (back to origin), step title, primary actions
top-right. Why here: the single largest *perceptual* gap to the incumbent —
every send and every signature passes through these screens. **This is where
the steward-directed parity mandate resumes.**

**9 · One-page accordion envelope setup** — source: spec §4 step 1,
checklist 8. Documents / recipients / message as three collapsible sections on
one page; inline validation on attempted progression; implicit drafts on
close. Replaces paged steps 1–2. Why here: with item 8 it completes the incumbent's
prepare flow shape; touching the wizard once for both avoids rework.

**10 · Tagging-canvas mechanics** — source: spec §4 step 2, checklist 1, 16.
Drag-from-palette with cursor ghost (keep click-to-arm as fallback), zoom
control, undo/redo, field copy/paste, grouped palette; multi-document
envelopes as separate files with per-file thumbnail cards. **Scope is under
`pumasi/DECISIONS.md` Q-016** (issue
[#4](https://github.com/pumasi-ai/pumasi-sign/issues/4), `escalated`): Option A
— cards over the existing upload-time merge, with the combination stated in
the UI *and in the certificate* — is the named default and may proceed
pre-`launched`; Option B (true per-document separation, backend rework) is not
authorized by that default. Why here: the canvas is "the product" per the
spec's own ranking; do it after item 8 so it lands inside the focus shell.

**11 · Signature identity: styles, saved list, frame imprint** — source: spec
§5 adopt modal, §8 signature adoption + framing, checklist 4. Generated styles
from name/initials with live preview, multiple saved signature/initials pairs
in a profile page, and the "signed by" bracket frame + short envelope/party ID
burned into the stamped PDF behind an account toggle (`service/src/core/stamping.ts`;
`backend/app/stamping.py` only if Q-018 keeps that tree). Why here: this is
what makes a signed document *look* like the incumbent's output — the artifact
everyone outside the org actually sees.

**12 · Post-sign share loop** — source: spec §5 finish sequence, checklist 12.
After Finish: share-by-email modal (multi-email chips, prefilled subject, short
message with counter), each recipient getting a tokenized free download link;
declining still completes. Why here: cheap, and it is the incumbent's growth
loop — the commons' S8 outward-transmission thesis for picking this product in
the first place.

**13 · Manager depth: bulk, folders, trash, richer filtering** — source: spec
§3, checklist 7, 21. Row checkboxes + bulk bar (download / move / delete), user
folders, a real Deleted view with restore (soft-delete; archive stays per-user
hide), quick-views dropdown, default date-window chip with inline clear,
two-line rows (title over "To: recipients"), density toggle. Why here:
daily-driver ergonomics once volume grows; none of it blocks the flows above.

**14 · Ceremony options** — source: spec §5, §8 signing settings, checklist 5,
23. Finish-later; configurable consent/disclosure step for remote recipients
(recorded in the certificate); auto-navigation modes (page-only / required /
all). Why here: recipient-facing polish and the compliance-relevant consent
record.

**15 · Field-type parity + per-recipient auth** — source: spec §4 palette,
checklist 17, 18. Email / Company / Title contact fields; Approve / Decline
action buttons; Note; per-recipient "Customize" auth (access code; SMS later).
Payment: explicitly skipped. Why here: each is small and spec-shaped; batch
after the canvas rework so new types land once.

**16 · Template library depth** — source: spec §7, checklist 9. Description
field, favorites, my/shared-with-me groupings, "[Untitled]" implicit drafts,
starter-template gallery. Why here: value scales with template count, which is
still small.

**17 · Admin & records layer** — source: spec §6, §8, checklist 3, 11, 13, 14,
20, 25. Account defaults (reminders/expiration, signing permissions, date/time
regional formats), per-user notification preferences, envelope/document custom
metadata, retention purge, combined-into-one-PDF + zip download, certificate
depth (per-signer viewed timestamps, security level, adoption method), a
Reports section. **The settings *shell* was pulled out as item 6**; this is
everything that goes inside it. Retention here is also what
[`STAGE.md`](STAGE.md) §2.4 needs to make a data-survival claim citable. Why
here: nothing user-visible upstream depends on it.

**18 · Onboarding polish** — source: spec §2, §9, checklist 15. First-run coach
marks per surface; persistent "n/5" getting-started checklist (banner + modal,
live progress). Why last: worth doing only once the surfaces it teaches
(items 7–11) are in their final shape.

---

---

## Blocked — not in the build order until a steward answers

Entries here have real work left, and **no coder may execute it today**. They
are out of the numbered list rather than sitting at its top, because the top
of that list is what the next coder packet builds, and a packet that takes an
entry nobody may execute delivers nothing. They come back into the order the
day their window closes, at whatever rank they then deserve.

**B1 · Make the landing page's licence claim true, then let users have it** —
source: issue [#8](https://github.com/pumasi-ai/pumasi-sign/issues/8)
(`accepted`, `priority: high`), [`STAGE.md`](STAGE.md) §2.3.
**This is what is left of the old item 1** after halves (a) and (c) were
delivered at `a49f594` (see Retired). Both remaining halves are steward-held
and **neither is released by CHARTER Part 0**:

- **(b)** *"Apache-2.0 (Open Source)"* is still on the page — the banner
  (`LandingView.vue:43`), the hero strip (`:80`) and the comparison table's
  License row (`:210`) — and this repository still carries no `LICENSE`.
  **`pumasi/DECISIONS.md` Q-021**, open; its named default is to add
  Apache-2.0 byte-identical to `pumasi-web/LICENSE`, **and nobody has taken
  it** — `pumasi-web` marketing job `0035` raised exactly that to the steward
  at 12:58 on 2026-08-31. Adding a licence is an outward grant a third party
  may rely on, which is why Part 0's reversibility rule does not release it.
  Frozen case `spec/0001` **A-005** pins those three strings byte-identical to
  `10a523d` and **retires with Q-021** — whichever way that entry lands, A-005
  is updated or deleted in the same commit.
- **(d)** then deploy — `wrangler deploy` from `service/`, **not** the Railway
  path (Q-018). **`pumasi/DECISIONS.md` Q-012**, open and explicitly outside
  Part 0's proceed-on-default rule. This entry does not ask for the deploy and
  does not schedule it; it records that #8 closes on one. Note the same deploy
  would carry ~6 commits of otherwise-unreviewed change; it should be
  deliberate, not incidental.

**Verified undeployed again this tick, not inherited.** Re-`curl`ed by the
fifth evaluation on 2026-09-01 at 00:29 UTC: the live bundle is still
`/assets/index-j38Qwibz.js` — the same filename the fourth evaluation recorded,
and the same one recorded before that. The route-table extraction below is the
fourth evaluation's and is **carried, not re-extracted**; the filename it was
taken from was re-confirmed, so nothing in it can have changed. The original
measurement:

```
$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/[^"]*\.js'
/assets/index-j38Qwibz.js
$ curl -s -o idx.js -w '%{http_code} %{size_download}\n' \
    https://sign.pumasi.ai/assets/index-j38Qwibz.js
200 839941
$ grep -oic 'landing' idx.js
0
```

Zero occurrences of `landing`, `LandingView` or `Apache-2.0` in 839 941 bytes.
This is a **stronger** measurement than a missing component chunk would be:
the route is registered eagerly by name (`frontend/src/router/routes.ts:15`,
`name: "landing"`, moved there from `router/index.ts` at `d18d534`) and only
its component is lazy-loaded, so the route *name* would be in the main bundle
even if the view were code-split — and `index.html` preloads no other chunk.

**This evaluation extracted the deployed route table rather than counting a
string, which settles it.** Every `path:` and `name:` literal in the bundle:
the paths are `/`, `/admin/users`, `/branding`, `/envelopes/:id`, `/login`,
`/privacy`, `/send/draft/:draftId`, `/send/:templateId?`, `/signed-out`,
`/sign/:submitterId`, `/sign/t/:accessUid`, `/templates`,
`/templates/:id/build`, `/terms` and the catch-all — and the route names
include `dashboard` and **not** `landing`. In the deployment, `/` is the
dashboard. One case-insensitive `beta` match exists in the bundle and it is
inside the CSS counter-style name `tibetan`, in a vendored library; the chip
is not there. **`LandingView.vue` has never reached a user**, which is not the
same claim as "its correction is undeployed" — see [`STAGE.md`](STAGE.md) §5,
where that row was wrong and is corrected in this pass.

**B2 · Carry #7's merged fix to the people it is for** — source: issue
[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) (`accepted`,
`priority: high`), [`STAGE.md`](STAGE.md) §5, `pumasi/DECISIONS.md` **Q-027**.
**New in this reorder.** The build is done and retired below; the user is not
served. Measured by this evaluation on 2026-08-31 at 20:10–20:12 UTC:

```
$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'
/assets/index-j38Qwibz.js
$ curl -s -i 'https://sign.pumasi.ai/api/auth/login?next=%2F'
HTTP/2 404
{"error":"Endpoint not found"}
```

and, decisively, **the deployed bundle still contains the helper `d18d534`
deleted.** Extracted from the shipped JavaScript by this evaluation — the
minified `loginRedirectUrl`, sitting beside `loginPageUrl`:

```js
function pl(e){return`/api/auth/login?next=`+encodeURIComponent(e)}
function ml(e){return`/login?next=`+encodeURIComponent(e)}
```

That is not an inference from a filename. It is the removed code, still
shipping.

**Re-measured by the fifth evaluation on 2026-09-01 at 00:29 UTC**, not
carried: `curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'`
still returns `/assets/index-j38Qwibz.js`, and
`GET https://sign.pumasi.ai/api/auth/login?next=%2F` still answers **404**.
Nothing has deployed. Note what this does and does not prove about `68e5d08`:
it establishes that **no deploy has carried a `frontend/dist` built at or after
`d18d534`**, which is the same bundle that would have to carry the envelope
guards, since `wrangler.jsonc` serves `../frontend/dist` and the worker ship
together. Q-031's own Status line says the same thing from the builder's side.

**Blocked on two entries, not one, and the second one is the finding.**

- **Q-012** — who carries a merged build to users — open, and explicitly
  outside CHARTER Part 0's proceed-on-default rule.
- **Q-021** — the licence — open, **and it binds this deploy too.**
  `service/wrangler.jsonc:8` serves `../frontend/dist` as one `ASSETS`
  directory, and `routes.ts:15` puts `LandingView` at `/`. `frontend/dist` is
  `.gitignore`d and must be rebuilt for the fix to be in it (`CLAUDE.md`: *"a
  stale `dist` ships a stale SPA"*). So **the only build that carries #7's
  repair also publishes `LandingView.vue`'s "Apache-2.0 (Open Source)"**
  (`:43`, `:80`, `:210`) on a repository that still has no `LICENSE`. The two
  cannot be shipped apart without a `frontend/` change nobody has proposed —
  which is Q-021's own named alternative, and is a decision, not a workaround.

Q-021's `Blocks` row names only the deploy that closes #8, because when it was
written #7's repair did not exist. It now holds a live user-facing defect fix
as well. **That is recorded here and raised as `pumasi/DECISIONS.md` Q-028
rather than routed around**; no seat here may weigh a licence question against
a broken sign-in button.

---

## Retired

**~~Repair the three unguarded envelope transitions~~ — delivered 2026-08-31
at `68e5d08`** (coder job `0058`, `spec/0006`, `pumasi/DECISIONS.md` **Q-031**,
7-day can-hurt window open, closes **2026-09-07**). **Was item 1.** Verified in
the tree at `56a8bf8` by this evaluation rather than taken from the decision
entry — the guards, their status codes and their current line numbers are in
the table at the top of this file. All three refuse before reading the request
body, so a refusing path writes nothing and audits nothing, and one predicate
(`isTerminal`, `durable.ts:109`) backs all three.

**This entry is retired with its own wrong sentence recorded, not deleted.**
The struck sentence, and it was this file's ranking argument for treating
`complete` as the least of the three:

> ~~So the omission mostly produces the **wrong refusal** — *"Already signed"*
> (409) where the other terminal states give *"no longer active"* (410) —
> rather than a wrong write.~~

**What disproved it:** the CC recipient. The reasoning rested on an envelope
only completing once every non-CC signer is `signed`, but the completion count
reads `AND is_cc = 0`, so a CC recipient is still `pending` at completion,
passes both guards, re-enters `finalize()` and writes a second `completed`
audit event — re-stamping the executed PDF where one is present. A reachable
wrong write. **Where the measurement lives:** `spec/0006/SPEC.md` **§S1a** for
the reasoning, frozen case **A-406** for the measurement (it asserted the
second completion event; the count was `2`), and `spec/0005` §S6.4, which had
it right before this file did.

**Two things this retirement does not claim.** It did **not** widen coverage —
the gate prints the same 21 assertions from the same four files as before the
release, re-run four times by this evaluation. And it did **not** falsify
[`VALUE.md`](VALUE.md) **C1**: the stamped PDF and its certificate live in R2
and a status overwrite never touched them. What was damaged is the row and the
audit log disagreeing with the certificate — **L-009** at row scale.

**Retired from the build order, and the defect is still live to every user.**
Q-031's own Status line says so, and this evaluation re-measured it at
2026-09-01 00:29 UTC: the deployed bundle is unchanged and nothing has been
deployed. The transitions behave the old way on `sign.pumasi.ai` today. That is
**Q-012**, not a build entry, and it is why this retirement is not a claim
about the product users meet — see [`STAGE.md`](STAGE.md) §2.6 and §5.

**Also recorded here because it belongs to this entry's history:** job `0058`
amended frozen cases **A-404**, **A-406** and **A-407** in the open, under the
default reading of **Q-030** (*may a builder amend a frozen acceptance case?*),
having read that question mid-run. **Q-030 is open**, `pumasi-tunnel` reverted
the same move under an objection, and nothing in this file pre-empts the
steward's answer. Two objections on this product cited CHARTER Part 3
requirement 2 against the amendment; both cite the **stale** copy of the
charter (**Q-032**), which is a fact about the objections and not an answer to
Q-030.


**~~#7: "sign in again" sends the user to a raw 404~~ — delivered 2026-08-31
at `d18d534`** (coder job `0037`, `spec/0003`, `pumasi/DECISIONS.md` **Q-027**,
7-day window open). Was item 1. **Verified by this evaluation in the source
tree, not taken from the job's report:**

- `SignedOutView.vue:2` imports `loginPageUrl` and `:6` sets
  `const signInUrl = loginPageUrl("/")`; `utils/http.ts:44` returns
  `"/login?next=" + encodeURIComponent(next)`.
- **`loginRedirectUrl` is gone.** `git grep loginRedirectUrl` over the tracked
  tree returns no definition and no caller — only a header comment at
  `utils/http.ts:39` explaining why it was removed, a frozen case at
  `frontend/src/signed-out-entry.spec.ts:153` asserting the name appears
  nowhere in the SFC, an old plan document, and a review file.
- The page it now targets answers on the deployed tree:
  `GET https://sign.pumasi.ai/login?next=%2F` → **200 `text/html`**, measured
  by this evaluation.

**Retired from the build order, and issue #7 stays open on purpose.** The
*build* is done; the user is not served. `sign.pumasi.ai` still runs the
pre-fix bundle — see [Blocked](#blocked--not-in-the-build-order-until-a-steward-answers)
**B2**, which is new, and [`STAGE.md`](STAGE.md) §5, where this is now the
worked example of *fixed in source and still wrong in production*.

**~~Make `GATE: PASS` cover the tree users actually meet~~ — delivered
2026-08-31 at `d18d534`** (coder job `0037`, `spec/0003`,
`pumasi/DECISIONS.md` **Q-025** rider (a)). Was item 2. Verified by this
evaluation by running it, not by reading it:

- The root `package.json` `test` script is now
  `npm run test:frontend && npm run test:service`; `test:service` is
  `.github/scripts/run-service-suite.sh`, which `npm ci`s, **builds**
  (`service/dist/` is `.gitignore`d and the suite runs `dist/`), runs the
  suite, and hands its output to `.github/scripts/assert-service-suite-ran.sh`
  — the **same file** `ci.yaml`'s `service` job calls, not a copy (L-007).
- Run at `d18d534` by this evaluation: `Test Files 6 passed (6)`,
  `Tests 85 passed (85)`, `# pass 2`, `# fail 0`,
  `assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled`. Before
  `d18d534` the same command reported 5 files / 69 tests and **zero** service
  assertions.
- Determinism re-measured for the suite that exists **today**, because the
  shape changed: **40 consecutive runs, 40 pass, 0 fail**, every run reporting
  the identical counts above. Details and method in [`STAGE.md`](STAGE.md) §0
  rider (b).

**What is carried forward, and it is now item 2.** The gate runs the served
tree. *Updated by the fourth reorder:* what it runs there is no longer "two
assertions against one file" — it is **21 across four files** at `f7c8d03`,
two of which drive a real Durable Object. The carried-forward complaint is
narrower now and is breadth, which is why the entry sits at **3**. `main` is still
**not a protected branch** — `GET /repos/pumasi-ai/pumasi-sign/branches/main/protection`
→ 404 *"Branch not protected"*, re-checked this tick — so this one hand-run
command remains the whole gate. Q-025 is untouched and stays open.

**~~Green main: fix the 4 backend pytest failures~~ — met 2026-08-31.** Was
item 1. CI run
[33410370102](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33410370102)
at `5cb3bf8`: `backend` ✓, `frontend` ✓, `e2e` ✓ (coder job `0018`; the four
failures were single-tenant expectations against multi-tenant normalization,
`1c8590d`, and `e2e` had two further causes, `5cb3bf8`). Retired rather than
deleted, with one thing carried forward: **that gate covers `backend/`, which
is not what users reach.** The re-sourced version of this entry's purpose —
*a gate whose green means something* — became the old item 2, retired directly
below. That entry's own successor — the *merge* gate, as against CI — was in
turn delivered at `d18d534` and is retired below it. What is left of the
lineage is item 3: a gate that runs the served tree, over a suite that is now
21 assertions wide and still leaves `worker.ts`, R2, mail, feedback and
conversion uncovered.

**~~Make the gate cover the tree users actually meet~~ — delivered 2026-08-31
at `ef851d6`** (coder job `0032`, `pumasi/DECISIONS.md` Q-018 parts (a), (b),
(c)). Was item 2. Confirmed independently by this evaluation rather than taken
from the job's report:

- `.github/workflows/ci.yaml` now defines **four** jobs — `backend` (`:10`),
  `frontend` (`:60`), **`service` (`:104`)** and `e2e` (`:144`). The `service`
  job checks out, `npm ci`s, **builds** (`dist/` is `.gitignore`d, so the
  build is not an optimisation), runs the suite through `tee`, and then runs
  `.github/scripts/assert-service-suite-ran.sh` against its own reported
  counts — deliberately independent of the build step, so deleting that step
  still turns the job red.
- Run [33420378497](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33420378497)
  on `main` @ `ef851d6`: `backend` ✓, `frontend` ✓, `service` ✓, `e2e` ✓.
- **The job can fail, and that was proven on real runs, not argued.** Run
  [33419949879](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33419949879)
  (`proof/service-break`): `service` **failure** while `backend`, `frontend`
  and `e2e` all succeeded. Run
  [33419950651](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33419950651)
  (`proof/service-unbuilt`): `service` **failure** on a tree with no build
  step — the exit-0-having-run-nothing trap (L-006), caught by the guard.
- `CLAUDE.md` now opens with *"there are two backends"*, names the worker as
  what serves `sign.pumasi.ai`, and carries Q-018 part (c) as a sentence
  rather than by deleting a job.

**Retired, not deleted, and what is carried forward:** Q-018 itself stays open
— nothing was deleted, the domain was not re-pointed, no data moved, and
*which tree is the product* is untouched. Two successors are in the order
above: the gate half this never covered was **the old item 2**, delivered at
`d18d534` and retired directly below; and the thinness of what the new job
runs is **item 2** (it was item 1 through the third reorder, then item 3; the two
deliveries at `3d01198` and `f7c8d03` are why it moved).

**~~Item 1(a): the `BETA` chip, and 1(c): the uncited competitor pricing~~ —
merged 2026-08-31 at `a49f594`** (coder job `0026`, under `spec/0001`).
Verified at `ef851d6`:

- **(a)** `LandingView.vue` no longer writes a rung. `frontend/src/stage.ts`
  exports `STAGE = "alpha"` as the single constant, with `STAGE_LABEL` and
  `STAGE_BADGE` derived from it by expression; the template renders
  `{{ STAGE_BADGE }}` and `in active {{ STAGE_LABEL }}`. The register stays
  `roadmap/STAGE.md` and frozen case **A-001** fails the build if the two move
  apart — L-007 closed by a gate rather than by a copy nobody checks.
- **(c)** the comparison table's figures now match
  [`MARKET.md`](MARKET.md) §1's cited pricing rows (DocuSign $11 / $30 / $45
  with the 5-per-month and 100-per-user-per-year limits; SignWell $10–$12 per
  **sender** and $30–$36 for three senders), read from each vendor's own page
  on 2026-08-31. The shipped `$25 – $65` and `$10 – $30` are gone, and
  `MARKET.md` — which did not exist at the last reorder — now does. Frozen
  cases **A-003** and **A-004** parse the figures and plan names out of
  `MARKET.md` at test time, so neither can fork from the file it checks.

Half (b) and the deploy (d) are **not** retired; they are B1 above.

---

Not copied, on purpose: plan-gating/upsell surfaces (Pumasi Sign is unmetered —
that is the pitch), SMS-delivery premium gating, payment fields, enterprise
admin consoles (permission profiles, CORS, API usage).
