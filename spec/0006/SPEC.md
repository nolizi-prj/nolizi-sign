# SPEC 0006 — Three transitions stop overwriting a finished envelope

**Intent:** [`INTENT.md`](INTENT.md) · window `pumasi/DECISIONS.md` Q-031.
**Takes:** `roadmap/BACKLOG.md` item **1** in full, and nothing else in that file.
**Amends:** `spec/0005` §S6.1, §S6.2 and §S6.4 — from *proposed* to *taken* —
and three of the four cases `spec/0005` §S4a marked RECORDED, NOT ENDORSED.
**Does not touch** §S6.3 (`expired`, item 2) or §S6's fifth finding (the OAuth
`email_verified` branch, unranked).
**Measured at** `0c043f8`, by the coder seat of job `0058`, 2026-08-31.

## S1 · The three defects, re-read rather than inherited

Line numbers below are **`0c043f8` before the change**. Nothing between
`f7c8d03` (where the product evaluation read them) and `0c043f8` touched
`service/src/`, and the three sites were re-read here to confirm it.

| | Site at `0c043f8` | What ran |
| :--- | :--- | :--- |
| **a** | `durable.ts:1239`–`:1244` | `cancel` — no status test of any kind. `UPDATE submissions SET status = 'cancelled'` and `audit(…, 'cancelled', …)` run unconditionally. |
| **b** | `durable.ts:1434`–`:1436` | `complete` — dead-envelope guard tests `cancelled` and `declined`, **not** `completed`. |
| **c** | `durable.ts:1490`–`:1500` | `decline` — none of `complete`'s three guards: no terminal-status test, no `me.status === 'signed'` test, no `submitterTurn` test. |

**S1a. `b` is a reachable wrong write, not merely a wrong refusal code, and
this spec says so because the register it came from says otherwise.**
`roadmap/BACKLOG.md` item 1 describes `b` as *"mostly the wrong refusal code
rather than a wrong write"*, reasoning that `if (me.status === 'signed')` at
`:1437` catches the reachable cases because an envelope only completes once
every non-CC signer is `signed`. **The quantifier is the error: `:1479` counts
`AND is_cc = 0`, so a CC recipient's status is still `pending` when the
envelope completes.** That recipient passes both guards, reaches `finalize()` a
second time and writes a second `completed` audit event — and where a PDF is
present, re-stamps the executed document (`spec/0005` §S6.4, which had it
right). This is not a reading: **frozen case A-406 asserted the second
completion event and the count was `2`**, and this seat re-ran it at `0c043f8`
to confirm before relying on it. `BACKLOG.md` is the product manager's register
and was not edited here; the correction is handed up in this packet's return
block instead.

## S2 · What the repair is

**S2a. `cancel` refuses every terminal status with `409`** — new guard, first
statement of the branch, **before** the request body is read:

```ts
if (isTerminal(sub.status)) return json({ error: 'This envelope is already closed' }, 409);
```

`draft` and `pending` remain cancellable, which is exactly the pair the shipped
`EnvelopeDetailView.vue:676` Void button is drawn for.

**S2b. `completed` joins `complete`'s dead-envelope guard**, keeping that
route's existing `410` and its existing wording, so the three terminal statuses
answer a signature attempt identically.

**S2c. `decline` takes `complete`'s three guards**, in `complete`'s order and
with `complete`'s wording, the terminal one at **`409`**:

```ts
if (isTerminal(submission.status)) return json({ error: 'This envelope is no longer active' }, 409);
if (me.status === 'signed') return json({ error: 'Already signed' }, 409);
if (!this.submitterTurn(me)) return json({ error: 'Earlier signers have not finished yet' }, 409);
```

**S2d. One predicate, not three copies** — `isTerminal` beside
`outSubmitterStatus` (`durable.ts:109`), because three hand-written status
lists is how the fourth transition acquires a fifth spelling.

**S2e. The `409`/`410` asymmetry is deliberate and is stated rather than
smoothed.** A finished envelope answers a signature with `410` and a decline
with `409`. `410` is what `complete` already returned for `cancelled` and
`declined`; changing it would alter an answer the shipped SPA reads today, for
no gain. `409` is what `BACKLOG.md` item 1's decision names for `cancel` and
*"the same treatment"* for `decline`, and it is what this route's other two
guards return. Both mean refused; neither writes. It is the one place the
outcome is not uniform, it is INTENT question 3, and a reviewer is entitled to
object to it.

**S2f.** No route gains a capability. No status the worker could not previously
write becomes writable. Nothing is deleted, no domain is re-pointed, no data is
migrated, `CLAUDE.md` is untouched, and no open `DECISIONS.md` entry is
answered, closed, dated or softened.

## S3 · Guard sites after the change

| Transition | Line | Code | Body |
| :--- | :--- | :--- | :--- |
| `cancel` | `durable.ts:1252` | **409** | `This envelope is already closed` |
| `complete` | `durable.ts:1452` | **410** | `This envelope is no longer active` |
| `decline` | `durable.ts:1513` | **409** | `This envelope is no longer active` |
| `decline` (already signed) | `durable.ts:1514` | 409 | `Already signed` |
| `decline` (out of turn) | `durable.ts:1515` | 409 | `Earlier signers have not finished yet` |

## S4 · The amendment of three frozen cases — in the open, in this commit

`spec/0005` §S4a marked four assertions RECORDED, NOT ENDORSED and stated that
**red there means someone took the backlog entry — a decision — and not that
the worker regressed.** Three of the four went red on purpose here. They are
amended in the same commit as the repair, each still asserting the transition
it was frozen for, now against the guard rather than against its absence.
**A-409 is untouched and still RECORDED, NOT ENDORSED**; `expired` is
`BACKLOG.md` item 2 and was not this packet's to take.

**Measured, not asserted:** the *unamended* `spec/0005` file was run against
the *repaired* `durable.ts` at this seat's own hand. Result:
**`# pass 18 · # fail 3`**, failing exactly `A-404`, `A-406` and `A-407` and
nothing else — `spec/0005`'s own predicted-mutation column, three mutations
applied at once instead of one at a time.

| Case | Asserted **before** | Asserts **now** |
| :--- | :--- | :--- |
| **A-404** — *"cancel has no status guard: it overwrites a completed, declined or already-cancelled envelope and audits again"* | For each of `completed`, `declined`, `cancelled`: `again.status === 200`; `statusOf === 'cancelled'` (the terminal status overwritten); `events === ['cancelled']`. And cancelling a pending envelope twice: `events === ['cancelled', 'cancelled']`. | For each of the same three: `409`; body `{ error: 'This envelope is already closed' }`; **`statusOf === status`** (survived); **`events === []`** (audited nothing). Cancelling twice: second call `409`, **`events === ['cancelled']`** — one, where it asserted two. Plus a new positive: a `draft` still cancels with `200`. |
| **A-406** — the RECORDED tail only; the case's first two thirds are unchanged | The CC recipient's post-completion signature accepted: `after.status === 200`, body `{ ok: true, status: 'completed' }`, and **`completed` event count `2`** — *"finalize ran twice"*. | `after.status === 410`; body `{ error: 'This envelope is no longer active' }`; `statusOf === 'completed'`; `signerStatus(cc) === 'pending'`; the whole audit trail **identical to a snapshot taken before the attempt**; **`completed` event count `1`**; and `completed_at` **unchanged**, proving `finalize()` did not re-run. |
| **A-407** — *"decline has no status guard where complete has one"* | Decline on a `declined` envelope accepted (`200`) and the second signer flipped to `declined`; a `completed` envelope overwritten to `declined`; a signer whose status was `signed` flipped to `declined`. | The three become `409` refusals with the row read back unchanged (`pending`/`completed`/`signed` respectively) and the audit trail **identical to a pre-attempt snapshot**. The case keeps its unchanged first half — one decline ends the envelope for everyone — and keeps the `complete`-refuses-with-`410` comparison, which is now a symmetry rather than the asymmetry it was frozen to expose. A fourth block is added for guard 3: declining out of turn is `409` *"Earlier signers have not finished yet"*. |

**S4-review. The ordering CHARTER Part 3 requirement 2 asks for was NOT
followed, and this is the one-line pass-through record Part 0 requires for
that.** Stated at the top rather than buried, because two reviewers caught it
and both were right on the clause they cited.

*What happened.* The frozen-case amendment and the implementation were written
together in one commit, and the cross-family **spec** review was taken after
rather than before. `reviews/20260831-181757-code-gemini.md` and
`reviews/20260831-181757-code-qwen.md` each returned a cited
`VERDICT: OBJECT` on exactly that — *"the builder modified existing frozen
acceptance tests in the implementation commit itself without first amending the
spec and passing a separate cross-family spec review"* — and
`reviews/20260831-182757-spec-qwen.md` objected again to the ordering after the
spec review was taken. **Neither family found a defect in the guards, in the
amended cases, or in this spec's substance;** all three objections are
governance and all three name the same clause.

*Why this proceeds rather than stalls, with the clause.* **`roadmap/STAGE.md`
records this product's stage as `alpha`** — re-read at `0c043f8`, not assumed —
and `governance/CHARTER.md` **Part 0** governs every requirement below
`launched`:

> *"Until a product's published stage (`roadmap/STAGE.md`) reaches
> **`launched`**, this charter **guides; it does not block** … **Process
> requirements yield to progress.** A requirement passed through is recorded in
> one line in the commit, not stalled on. The debt register still catches
> patterns."*

The freeze ordering is a process requirement. It is **not** on Part 0's
never-suspended list, which is `HUMAN.md` and irreversible acts — and this is
neither: no money, no credential, no mail, no published personal data, and
`git revert` undoes all of it. **So this is a Part 0 pass-through, recorded
here and in one line in the commit, exactly as Part 0 says to handle it — not
a clause argued past.**

*What was not skipped.* The spec review was **taken**, not waived, and it is
the thing the freeze exists to buy: a family other than the builder's judging
whether these three cases were amended toward the guard or bent toward the
code. `reviews/20260831-182757-spec-gemini.md` returned `APPROVE` on that
question. `roadmap/BACKLOG.md` item 1 authorized the amendment before this
packet was written; it did not, and could not, waive the review, and the review
was not waived.

*What the next seat should take from this.* The honest lesson is that a packet
which authorizes a frozen-case amendment should also say **take the spec review
first**, and this one did not — it said amend in the same commit as the repair,
which is the ordering the charter's Part 3 spends a paragraph forbidding. That
is handed up in this job's return block as a packet defect, not a reviewer
error. At `launched` this run would have stopped here.

**S4-Q030. While this packet ran, the commons raised the very question these
objections turn on — and its named default is the route this section took.**
`pumasi/DECISIONS.md` **Q-030**, *"May a builder use CHARTER §3 requirement 2's
own remedy to amend a frozen acceptance case?"*, was committed to `pumasi` at
`7a0892d`, 2026-08-31 18:57 CDT — while this work was in review — raised from
`pumasi-tunnel` job `0059` out of job `0047` meeting the same clause. It is
**open**, it is the steward's, and nothing here closes, dates or softens it.

Its **default on silence** is that requirement 2's remedy **is** available to
the builder, on the conditions the clause states: amend the spec **in the
open** — a numbered amendment saying what changed and why, never a silent edit
— and take a **fresh cross-family spec review** before building against it.
That is what §S4-review records having done, in that form, with the ordering
deviation named rather than hidden.

Its two riders, checked against this change rather than assumed:

- **(a) "The freeze protects assertions, not fixtures."** This amendment is the
  *harder* kind and says so: it changes what A-404, A-406 and A-407 **assert**,
  not how they are set up. Under rider (a) that is a change to the standard and
  a reviewer must weigh it as one. `reviews/20260831-183823-spec-gemini.md` did
  weigh it as one — it records the cases moving *"from defect characterization
  (`RECORDED, NOT ENDORSED` in `spec/0005`) to active guard enforcement"* — and
  approved. §S4's table exists so that weighing is possible at all.
- **(b) "The spec reviewer of the amendment must not be the code reviewer of
  the change that follows, where three or more families are available."**
  Satisfied, and not by accident: the amendment's spec review is **gemini**
  (`reviews/20260831-183823-spec-gemini.md`, APPROVE) and the code review is
  **kimi** (`reviews/20260831-185008-code-kimi.md`, APPROVE). Different
  families, and `tools/families.sh` reported 5 of 6 available on the day.

**This is a second instance for that entry and it differs from the first in the
way that matters**: `pumasi-tunnel`'s A-10 was a *fixture* amendment, rider
(a)'s easy case; this one changes assertions. Handed up as evidence, not as an
answer.

**S4-charter. There are TWO charter files on this machine, they disagree about
exactly this clause, and that — not a disagreement about the code — is what
split the reviewers.** Found while resolving the objections above; reported
because it will mislead the next run too.

| Path | Last commit | Contains Part 0? | Header |
| :--- | :--- | :--- | :--- |
| `pumasi/governance/CHARTER.md` — the copy `pumasi-ops/roles/coder.md` and `DRIVER.md` name as the source | current | **yes** | `Version: 0.4-draft · Status: Proposed` |
| `/home/m/dev/governance/governance/CHARTER.md` — a checkout of `github.com/pumasi-ai/governance`, `main`, **ahead 1** | **2026-08-29 15:51 CDT** | **no — `grep -c 'Part 0'` is `0`** | `Version: 0.4-draft · Status: Proposed` |

The steward added Part 0 on **2026-08-30**, a day after that checkout's last
commit. **Both files carry the same version string**, so nothing in either
header tells a reader which one governs.

**This is verifiable in the reviewers' own transcripts, by the paths they
themselves cited.** The same family reached opposite verdicts in the same hour
on the same work:

- `reviews/20260831-183823-spec-gemini.md` cites
  `file:///home/m/dev/pumasi/governance/CHARTER.md` — the copy with Part 0 —
  applies it with line citations, confirms `alpha` out of `roadmap/STAGE.md`,
  and returns **`VERDICT: APPROVE`**.
- `reviews/20260831-185008-code-gemini.md` cites
  `file:///home/m/dev/governance/governance/CHARTER.md` — the copy **without**
  Part 0 — quotes Part 3 requirement 2 as unqualified, and returns
  **`VERDICT: OBJECT`**.

Its objection is therefore **cited but against a superseded text**, and it is
recorded here in full rather than discarded quietly: on the governing copy the
clause it quotes is not unqualified, and Part 0 supplies the pass-through this
section discharges. `reviews/20260831-185008-code-kimi.md` reached that
conclusion independently — *"a clause the charter itself converts to a
recorded, non-blocking pass-through at this product's published stage … At
`launched` this same commit would be objectionable; at `alpha` … it is not"* —
and returned `VERDICT: APPROVE`. **No family found a defect in the code, the
amended cases or this spec.** Four transcripts across three families raise
governance and nothing else.

**This seat did not edit either charter.** Both are outside a coder's write
list, and one of them is another repository entirely. It is handed up in this
job's return block and `DIGEST.md` as the thing to fix, because it is
[L-007](https://github.com/pumasi-ai/governance/blob/main/lessons/L-007-restating-a-rule-forks-it.md)'s
shape — a rule restated in a second file forks — applied to the charter itself,
and because `tools/review.sh` gives an agentic reviewer no way to say which
copy governs.

**S4a. Each amended case carries its own before/after at its header**, naming
`spec/0006` §S4 and the `spec/0005` §S6 entry it retires, so the record does not
depend on a reader finding this file. The file's top-of-file comment is updated
in the same commit for the same reason.

**S4b. "Writes nothing and audits nothing" is proved, not inspected.** Every
refusing path in all three cases reads the row back out of the store and
compares the audit trail against a snapshot taken immediately before the
attempt. Snapshotting rather than asserting `[]` is deliberate where a signer
cookie is involved: verifying a signer writes `signer_verified`, and that write
is not the one under test (`spec/0005` §S3's harness note, `pumasi/lessons`
L-006 on order-dependent trails).

## S5 · Where this stops

**Not taken, stated rather than left to be discovered:**

- **`expired`** (`spec/0005` §S6.3, `BACKLOG.md` item 2) — needs a `scheduled`
  handler and a cron trigger designed on purpose. Untouched; A-409 still
  records the gap.
- **The OAuth `email_verified` branch** (`durable.ts:766`) — `spec/0005` §S6's
  fifth finding, unranked, uncharacterized, and outside this item.
- **No new coverage** of `worker.ts`, `storage/r2.ts`, `mail.ts`,
  `feedback.ts`, `convert/graph.ts`, envelope creation, correction, `copy`,
  templates or any file route. `spec/0005` §S5's limits stand unchanged.
- **`expired` is deliberately NOT in `isTerminal`.** A-409 records that the
  worker never writes that status, so no envelope can be in it; adding it would
  be a guard against a state the deployed tree cannot reach, and it belongs
  with `BACKLOG.md` item 2, which will make the status reachable. Raised as an
  observation by `reviews/20260831-181757-code-qwen.md` §3 and answered here.
- **`finalize`'s stamping branch** is still not reached by these cases. A-406
  proves the second `finalize()` did not run via `completed_at` and the event
  count; it does **not** prove the re-stamp is prevented at the R2 level,
  because no case in this file gives an envelope a PDF.

**This change does not move the number the gate prints, and no release note or
stage claim may read it as widening coverage.** `service/` remains thin —
that is `BACKLOG.md` item 3, and it is not retired here.

## S6 · Out of scope, stated so a reviewer can hold it

`backend/` (Q-018 — a tree no user reaches; untouched) · `frontend/` (read for
INTENT's evidence, not modified) · `roadmap/BACKLOG.md` and `roadmap/STAGE.md`
(the product manager's registers) · `pumasi/catalog.json` (Q-019) ·
`pumasi/HUMAN.md` · `CLAUDE.md` · deployment of any kind (Q-012, Q-018).
