# STAGE — Pumasi Sign

**Current stage:** `alpha`
**Set:** 2026-08-31, first publication of this file, at `5cb3bf8`.
**Re-evaluated:** 2026-09-01 (**sixth evaluation**), at `2471a29`. **Stage
unchanged** — not promoted, not demoted. Evidence re-derived below, not carried.

**What this evaluation changed is every row that rested on the sentence
*nothing has deployed*. Something deployed.** For the first time in this
file's life the live host moved: the bundle went `/assets/index-j38Qwibz.js` →
**`/assets/index-CnoFAC2c.js`**, `/` is now the landing page, and **five of
§5's seven rows moved with it**. Four of them moved in the good direction and
retire. **One moved in the bad direction and is the most serious thing on this
page:** *"Apache-2.0 (Open Source)"* was **merged and never shipped**; it is
now **served to the public from a repository that carries no `LICENSE`**, which
is `pumasi/DECISIONS.md` **Q-021** with its central premise — *"Not yet public
… which is the whole reason this is a question and not an incident"* —
overtaken by an event rather than by an answer.

**The stage did not move, and the reason is not caution.** Four merged repairs
reaching users is not a rung: it retires four *gaps*, it does not create the
*evidence* the next rung needs. Coverage, data-survival, PR-1 and the licence
are all where they were, and the deployment that closed those gaps opened a
new one that no previous evaluation could have — the product now publishes an
untrue licence grant to strangers. A page that is live and wrong is not
progress toward `beta`; it is the same distance, measured from a worse place.

**Which tree this file's stage sentence is a claim about — stated because
Q-018 is open and the answer changes what `alpha` means here.** It is a claim
about **the Cloudflare Worker in `service/`, plus the SPA it serves** — what
answers `sign.pumasi.ai` and what a user actually meets. It is **not** a claim
about `backend/`, which no user reaches and which this file has never rated.
Where the two trees disagree — notably on who may hold an account — this page
records the worker's behaviour. That choice is **not** an answer to Q-018: it
is the observation that `alpha` on the ladder means *works for people who talk
to the builders*, and the people talking to the builders are using the worker.
**Stage 1 exit gate:** **NOT MET — and the reason changed completely at this
evaluation, which is why the two words are the same and mean something
different.** `STAGE_PLAYBOOK.md` Stage 1 reads: *"Pure-core test suite passes
100%; both public landing surfaces are live."* Through five evaluations the
unmet half was **Surface B is not live**. It is live: re-extracted from the
deployed bundle by this seat at 2026-09-01 01:57 UTC, the route table's first
entry is

```js
{path:`/`,name:`landing`,component:()=>Wl(()=>import(`./LandingView-C5khdw3s.js`),__vite__mapDeps([0,1,2,3])),meta:{public:!0}}
```

(§2.2). Surface A has been live since the first publication of this file, and
the served tree's suite passes — **28 assertions across five files**, `# fail 0`
(§2.1).

**On the literal words, the gate now reads met. This seat does not record it
as met, and states the ground rather than the reluctance.** Stage 1's own
objective is *"Day-1 landing pages with honest stage calibration"*, and its
Surface B deliverable requires *"explicit capability and limitation statement
to set honest customer expectations"*. The page that went live carries the
correct rung (`ALPHA — ACTIVE DEVELOPMENT`, derived from this file — §2.3.1)
and correctly cited competitor pricing (§2.3.3), and it also carries **three
claims that Apache-2.0 governs this code, on a repository that grants no
rights** (§2.3.2). A surface is not "honestly calibrated" while one of its
claims is untrue, and the untrue one is a licence grant a stranger may act on.
**So the gate is `NOT MET` on Surface B's honesty, not on its existence**, and
what flips it is **Q-021** answering in either direction — not a build, and not
this seat.

**`STAGE_PLAYBOOK.md` Event 3 therefore did not fire and must not**, which
matters more this evaluation than in any before it: Event 3 auto-enqueues a
marketing packet to *publish stage-promotion announcements and update public
stage badges*, and firing it today would put a second Pumasi surface behind the
same unbacked claim. **No gate figure is quoted from here into anything
public** — **Q-024** (does a gate stay `MET` against a suite that fails?) is
open fleet-wide, and this reading is `NOT MET` in any case.
**`STAGE_PLAYBOOK.md` Event 3 did not fire**, and could not: Event 3 fires when
this role confirms a Stage Exit Gate is `MET`, and this evaluation confirms the
opposite. No promotion announcement is owed to the marketing manager.
**Stage 2 (`beta`) work:** not started as a labelled effort. What holds the
`beta` label back is listed under "Why not `beta`", and every item there is a
`BACKLOG.md` entry.

Owned by the product-manager role
([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md),
duty 6). The stage ladder and its meanings are that file's table; the
stage-by-stage gates are
[`pumasi-ops/STAGE_PLAYBOOK.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/STAGE_PLAYBOOK.md).
Neither is restated here (L-007) — this file records only *which* rung, on
*what* evidence, and what the next one costs.

**The stage is set by evidence, not by aspiration or by a chip.** The `BETA`
chip that the first publication of this file disagreed with is **gone from the
source** — `a49f594` replaced it with a constant derived from this file.

**Two evaluations argued about whether that chip was live. It is live now, and
it says `ALPHA`.** The second evaluation filed it as *fixed in source, still
wrong in production*; the fifth corrected that to *merged, never shipped* and
was right at the time. The sixth measures it deployed: the served landing chunk
opens `var g=`alpha``, derives `ALPHA — ACTIVE DEVELOPMENT` from it by
expression, and renders *"Pumasi Sign is in active Alpha"* — so the constant
`a49f594` derived from **this file** is what a stranger reads on the product's
front page (§2.3.1). **No user has ever seen a `BETA` badge on this product**,
and now none can: the badge is generated from the rung this file sets, and
frozen case **A-001** fails the build if the two move apart.

**That is the one place where the deployment made this page's job easier, and
it is worth naming, because everything else it did was to move a claim from
private to public.** The same bundle carries the honest stage badge and the
dishonest licence row. They shipped together, from one `frontend/dist`,
which is exactly the entanglement **Q-028** was raised to record — and it
resolved itself by shipping rather than by anyone answering it.

---

## 0 · How the evidence on this page was produced

`pumasi/DECISIONS.md` **Q-025** asks what a quality claim in a file like this
one is actually asserting. Its default carries three riders. This section
answers all three at the top, before any number below is read.

### Rider (a) — no `GATE: PASS` without naming who re-ran it and when

**This file has never cited `GATE: PASS`, and does not begin now.** Checked
rather than assumed: the string `GATE: PASS` does not occur in this file's
history. What §1 cited at first publication was a **CI run URL**
([33410370102](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33410370102)),
which is the *stronger* artefact the rider is reaching for — a third party can
re-open it. So there is nothing to correct here, and recording that is the
honest response to the rider rather than manufacturing a correction.

What this table records is the other half of the rider — **who and when** — for
every claim on this page. Rows marked `56a8bf8` were re-run **by the fifth
evaluation**, on 2026-09-01 between 00:10 and 00:35 UTC. Rows marked otherwise
were **not** re-run this tick and say so. The fifth evaluation **reversed the
fourth's `inherited` marking on the live-host row** — it did `curl` the
deployment — and added the number of runs behind the suite figures, which the
fourth recorded as one.

| Evidence | Who re-ran it | When |
| :--- | :--- | :--- |
| **Root `npm test` (= `gate.sh` step 1) at `56a8bf8` — 21/4 and 85/6** | **the fifth evaluation, locally — root `npm test` ×3 plus `service/` `npm test` ×1; service assertions rest on 4 runs, the guard line on 3, the frontend figures on 2 runs *read*** | **2026-09-01 00:10–00:35 UTC** |
| **`service/src/test/` contents — four files, `e2e-workflow.test.ts`'s four imports** | **the fifth evaluation, reading the tree at `56a8bf8`** | **2026-09-01** |
| **The three transitions now guarded (`durable.ts:1252`, `:1452`, `:1513`; `isTerminal` at `:109`)** | **the fifth evaluation, reading the tree at `56a8bf8`** | **2026-09-01** |
| **Absence of `scheduled` / cron (`grep` over `worker.ts`, `wrangler.jsonc`)** | **the fifth evaluation, at `56a8bf8`** | **2026-09-01** |
| **Live host: bundle filename `/assets/index-j38Qwibz.js`; `/api/auth/login?next=%2F` → `404`** | **the fifth evaluation, via `curl` — this row was `inherited` at the fourth and is not now** | **2026-09-01 00:29 UTC** |
| **Absence of `RISK_ZONES.yaml`; `pumasi-booking`'s two, both nested below its root** | **the fifth evaluation, via `ls` + `git ls-files` over five repositories** | **2026-09-01** |
| **`PRODUCT-RULES.md` absent from `pumasi` main (`3bc1822`); present only at `0115758`** | **the fifth evaluation, via `ls` + `git log --all`** | **2026-09-01** |
| **Root `package.json` still has no `version`; `FeedbackDialog` auto-attaches; `/branding` route at `routes.ts:69`** | **the fifth evaluation, at `56a8bf8`** | **2026-09-01** |
| **#6 / #10 / #11 still open, `accepted`, `priority: normal`** | **the fifth evaluation, via the tracker** | **2026-09-01** |
| **`catalog.json` both arrays** | **the fifth evaluation, at `pumasi` @ `3bc1822`** | **2026-09-01** |
| Deployed bundle **contents and route table** (no `landing` route; `/` is the dashboard) | the **third** evaluation — **carried**, but taken from the bundle filename the fifth re-confirmed, so it cannot have changed | 2026-08-31 |
| `expires_at` is user-settable and its meaning is stated in the SPA's copy (`SendView.vue`, `EnvelopeDetailView.vue`) | the **fourth** evaluation — **carried**; `0058` touched neither file | 2026-08-31 |
| Void button gating (`EnvelopeDetailView.vue:676`); no `decline` call site in `frontend/src` | the **fourth** evaluation — **carried** | 2026-08-31 |
| `LoginView.vue:120`/`:123` MDI glyphs; `pumasi-booking` `pages.ts:1505`/`:1507` brand SVGs | the **fourth** evaluation — **carried** | 2026-08-31 |
| The OAuth guard's line number (`durable.ts:766`) | the **fourth** evaluation — **carried, not confirmed**; `0058` moved lines in that file | 2026-08-31 |
| CI run 33430138500 (`main` @ `d18d534`, four jobs) | the **third** evaluation — **inherited**; no CI was checked at `56a8bf8` | 2026-08-31 |
| Branch protection on `main` (404 *"Branch not protected"*) | the **third** evaluation — **inherited** | 2026-08-31 |
| Determinism, 40 consecutive runs | the **third** evaluation, against a **different suite shape** — see rider (b) | 2026-08-31 |
| `backend/` pytest (541 functions) | **nobody, here** — see rider (b) | — |
| `frontend/` Playwright e2e (6 specs) | **nobody, here** — see rider (b) | — |
| The `service` job's ability to **fail** (runs 33419949879, 33419950651) | the **second** evaluation, not this one — cited as its finding | 2026-08-31 |

**And the merge gate is no longer unwitnessed on the served tree.** This is the
one line in this section that changed, and it changed because `BACKLOG.md`'s
old item 2 was delivered at `d18d534`. `pumasi/tools/gate.sh:25` still runs
`npm test` at this repository's root; that script is now
`npm run test:frontend && npm run test:service`, and `test:service` is
`.github/scripts/run-service-suite.sh` — install, **build** (`service/dist/` is
`.gitignore`d), run, then hand the suite's own output to
`.github/scripts/assert-service-suite-ran.sh`, the *same file* `ci.yaml` calls
rather than a copy of it (L-007). Run by the fifth evaluation at `56a8bf8`,
three times, identical every time:

```
Test Files  6 passed (6) · Tests  85 passed (85)
# pass 21 · # fail 0
assert-service-suite-ran: 21 passing, 0 failing, from 4 compiled
```

**What that does and does not buy, stated so the next reader does not
over-read it.** `GATE: PASS` on this repository carries a number about the tree
that answers `sign.pumasi.ai`. **The number is 21 across four files** — it
was 2 across two through the third evaluation, this page said so three times
after it stopped being true, and it did **not** move at `68e5d08`. Two of the four files drive a real Durable
Object; two are the PDF stamper. What it still does **not** cover is in §2.1.
And the gate is still one command a coder runs by hand: `GET
/repos/pumasi-ai/pumasi-sign/branches/main/protection` → **404 "Branch not
protected"** — **inherited from the third evaluation, not re-checked this
tick** — so CI reports and blocks nothing. Q-025's question — *is `GATE: PASS`
an agent's own report?* — is untouched and its entry stays open. What closed is
the narrower complaint that the report excluded production. `BACKLOG.md`
**item 2** is what is left.

### Rider (b) — measure determinism, do not inherit a single green run

**The determinism figure on this page is now stale, and this evaluation did
not refresh it. That is stated rather than papered over.** The third
evaluation's 40/40 was measured at `d18d534`. Since then `spec/0004` and
`spec/0005` added nineteen assertions to the service half, so **the suite the
40 runs measured is not the suite that exists today** — the same reasoning that
retired the second evaluation's figure now retires the third's.

**What this (fourth) evaluation actually ran: one run of the current command,
plus one separate run of the frontend half.** One run is not a determinism
measurement and is not offered as one. The counts are in rider (a); the honest
rate for `f7c8d03` is **1 of 1**, which establishes that the suite passes and
establishes nothing about flakiness.

**Why this seat did not run 40.** Nothing prevented it; it was a judgement
about where this packet's time was worth spending, and the reader is entitled
to know that rather than to find a number with no runner's name on it. A
repeat-run pass belongs in whichever evaluation next needs to make a
reliability claim — and one will be needed before any `beta` argument, because
`beta` means strangers can rely on it. **Recorded as a gap in this page's
evidence, not as a result.**

Raw counts, and the number of runs actually performed. **The `d18d534` row is
retained as history and is explicitly labelled as measuring a retired suite
shape:**

| Suite | Runs | Result | Per-run counts |
| :--- | ---: | :--- | :--- |
| **Root `npm test` at `f7c8d03` — the command that exists today** | **1** | **pass** | `Test Files 6 passed (6)`, `Tests 85 passed (85)`, `# pass 21`, `# fail 0`, `assert-service-suite-ran: 21 passing, 0 failing, from 4 compiled`. **One run. No determinism claim.** |
| Root `npm test` at `d18d534` — **a suite shape that no longer exists** (2 service assertions, not 21) | 40 | 40 pass, 0 fail | identical on every run: `Tests 85 passed (85)`, `# pass 2`, `# fail 0`, `2 passing, 0 failing, from 2 compiled`. **History; does not describe `f7c8d03`.** |
| `backend/` pytest — 541 test functions | **0** | **not run, not inherited** | — |
| `frontend/` Playwright e2e — 6 specs | **0** | **not run, not inherited** | — |

**One command, not two, and that is still the shape.** The frontend and
service halves are reached by the single root `npm test`, and the `service`
half is `npm ci` → `npm run build` → `node --test dist/test/*.test.js` → guard,
from scratch. The third evaluation's exact command, kept for reproducibility:

```
for i in $(seq 1 40); do npm test; done   # repository root, at d18d534 — NOT re-run at f7c8d03
```

**On the two suites that could not be repeated, and why the number is 0 rather
than an estimate.** Re-checked this tick rather than carried: `backend/` pytest
is Postgres-only by design, and on this machine `pg_isready` is **not on
`PATH`** at all while a TCP connect to `127.0.0.1:5433` is **refused**;
`docker` is **not on `PATH`**, so the container the README prescribes cannot be
started either. The Playwright job drives a Docker image of `backend/` and
fails for the same reason. **No rate is reported for either, because none was
run.** CI ran both green at `d18d534` (run 33430138500) — that is one
observation, from CI, and it is recorded as one observation. Note what §2.1
(iii) says about what that observation is worth on this product: `e2e` was
green at `ef851d6` *because* the defect existed.

**The one run this evaluation performed was checked the same way a
determinism run would be, which is the part that carries over.** `service`'s
`test` script is `node --test dist/test/*.test.js` against a `.gitignore`d
`dist/`, and an unbuilt tree exits **0** having run nothing (L-006; frozen case
`spec/0002` A-103 pins exactly this) — so exit status alone proves nothing.
This seat read the **reported assertion counts**: `# pass 21`, `# fail 0`, and
the guard's own line `21 passing, 0 failing, from 4 compiled file(s) for 4
source file(s) under service/src/test`. That establishes the build happened and
the assertions ran. It does not establish that they always do.

**Context, not a claim about the fleet:** `pumasi-booking` measured 40 of 40
(job `0030`) and `pumasi-tunnel` reported 3 failures in 40 (**Q-024**, whose
own record has since been complicated by a port-collision finding — not this
product's business, and cited only so the comparison is not read as settled).
The third evaluation's 40 of 40 was a good answer on the one suite that could
run *then*; it says nothing about the 541 nobody re-ran, nothing about the
suite that exists now, and **it was never a coverage claim** — a deterministic
suite is deterministic at whatever width it has, which is `BACKLOG.md` item 2.

### Rider (c) — CI-derived evidence and seat-derived evidence, ranked

No demotion is taken for lacking CI, and none is warranted: this product
**has** CI, and since `ef851d6` it covers the served tree. The rider's real
instruction is the other one — evidence re-derived by a seat that did not write
the code is **weaker than CI, and is written down as weaker**. Applied here:

- **Strongest — CI artefacts.** Run 33430138500 at `d18d534` (`backend` ✓
  `frontend` ✓ `service` ✓ `e2e` ✓), and the second evaluation's runs
  33419949879 and 33419950651, two *failures* deliberately produced to prove
  the `service` job can go red.
- **Middle — live-host measurement.** The `curl` results in §2.2 and §2.1.
  Reproducible by anyone with the URL, but they measure the deployment at one
  moment and this seat ran them.
- **Weakest — this seat reading source and running suites locally.** The 40-run
  figures, the file-content findings in §2.1 and §2.4, and the issue verdicts.
  Nobody but this evaluation has seen them. Where a claim below rests only on
  this tier it says so.
- **Absent.** Anything about `backend/`'s 541 tests beyond CI's single green
  run, and anything about `service/`'s untested modules (§2.1) — there is
  nothing to be weak *about* there.
- **Weaker still than any of the above, and named because it exists: an
  *uncommitted* file.** `reviews/20260831-143359-code-qwen.md` is a
  cross-family code review of `2bd3ba7..d18d534` that is **untracked in the
  working tree** — it is in no commit, would vanish on a clean checkout, and
  this seat may not commit it (`reviews/` is not on the product-manager role's
  May-write list). This evaluation read it and **it contains no findings**: 9
  lines, 464 bytes, a header and a horizontal rule, where the two committed
  gemini reviews of the same range are 72 lines each. Its header records why it
  exists — *"`pumasi/tools/review.sh` has no case for this family — it knows
  only claude, gemini and grok"* — so it was driven by hand. **Nothing on this
  page rests on it**, and the release note's and Q-027's breadth claim of *one*
  non-builder family (gemini) is not contradicted by it: the file is dated
  2026-08-31T19:33:59Z, twelve minutes *after* the release note was committed
  (`pumasi` `4e9bcc7`, 19:21:34 UTC), and an empty review adds no breadth in
  substance. Recorded as a defect in the review tooling, not as evidence.

**Breadth achieved (D-104).** `pumasi/tools/families.sh` reports **1 of 3
families available** this tick and prints the D-104 notice. `grok` answers
`HTTP 402 "Grok Build usage balance exhausted"` — a **billing** failure, not an
availability one, and `families.sh` reports it as `UNREACHABLE` because it
cannot tell the two apart. `gemini` (`agy`) answers. This evaluation edits no
product code and takes no merge gate, so no cross-family code review was owed;
the breadth is recorded because it was measured, not because it was spent.

---

## Maturity gates

| Stage | Criteria (STAGE_PLAYBOOK.md) | Status |
| :--- | :--- | :--- |
| **0 · Candidate** | Steward selection | **COMPLETE** — built and deployed |
| **1 · Alpha** | Pure-core suite passes 100%; **both** public landing surfaces live | **IN PROGRESS — NOT MET, on the second half only.** First half **met and measured this tick**: the pure core (`core/stamping.ts`) passes 2/2, 40 runs of 40, identical counts (§0 rider (b)). Second half **not met**: Surface A is live; Surface B has **never been deployed** — the live bundle registers no `landing` route at all (§2.2). **Event 3 does not fire.** |
| **2 · Beta** | Real end-to-end users complete workflows without engineer intervention | PENDING |
| **3 · Launched** | Production hardening, cross-model regression, 7-day veto window | PENDING |

---

## 1 · What is true, measured this tick

Measured 2026-09-01 against `main` @ `2471a29`, by running the commands rather
than by reading the claim. **Provenance per §0 rider (a), which marks which
rows this evaluation re-ran and which it carried.** Every live-host row below
was re-measured by this seat between **01:56 and 02:06 UTC**, and none is
inherited from job `0064`'s 01:11 UTC reading — which is deliberate, because
one of that reading's four conclusions did not survive re-measurement (§2.2).
The CI row was not re-run.

**CI was green on `main` at the last evaluation's commit — inherited, not
re-run here.** Run
[33430138500](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33430138500)
at `d18d534`: `backend` ✓, `frontend` ✓, **`service` ✓**, `e2e` ✓. **This
evaluation did not check CI at `56a8bf8`**, so no green is claimed for the four
commits since. **The qualification that attaches to this sentence is the whole
of §2.1, and it has not gone away**: four green jobs sat over a defect that is
live in production right now (§2.2).

**The merge gate runs the served tree, and this is the first evaluation at
which what it runs there grew.** Root `npm test` at `2471a29`, run by **this**
evaluation on 2026-09-01 at 02:03 and 02:05 UTC — **2 runs, identical**:
`Test Files 6 passed (6)`, `Tests 85 passed (85)`, **`# pass 28`**, `# fail 0`,
**`assert-service-suite-ran: 28 passing, 0 failing, from 5 compiled`**.

**21 across four files → 28 across five.** `2471a29` added
`service/src/test/envelope-expiry.test.ts` (A-410–A-416) and, per the coder's
own report, **A-415 is the first assertion in this repository that drives
`service/src/worker.ts` at all**. Three previous evaluations recorded a repair
that widened no coverage; this one records the opposite, and it is the only
figure on this page that moved for a reason other than a deploy.

**Both defects that coverage found are now repaired in source, and exactly one
of the two repairs has reached a user.** The three unguarded envelope
transitions were fixed at `68e5d08` and the deployment of 01:02 UTC **carried
them** — §5's state (iii) is empty for the first time since it was defined
(§2.6(i)). The customer-set `expires_at` the worker never acted on was fixed at
`2471a29`, seven assertions and an hourly cron trigger, and it is **not**
deployed: the live worker's handler list is `fetch` alone (§2.6(ii)). So the
product gained one repair and the repository gained another, and the gap
between the two is the same gap **Q-012** has named since it was raised.

**The product is live, answers, and — for the first time — answers with a build
that is not months of repairs behind `main`.** Re-run by this seat:

```console
$ date -u; curl -s https://sign.pumasi.ai/api/health
Tue Sep  1 01:59:28 AM UTC 2026
{"status":"ok","service":"pumasi-sign","time":"2026-09-01T01:59:29.010Z"}

$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'
/assets/index-CnoFAC2c.js

$ curl -s -X POST https://sign.pumasi.ai/api/auth/dev-login
{"error":"Endpoint not found"}
```

The bundle filename moved for the first time in this file's history
(`j38Qwibz` → `CnoFAC2c`), and the last line is still the worker's error body
rather than FastAPI's `{"detail": …}` — so Q-018's factual half is unchanged:
**the worker is what users meet.** What the deployed build *is*, dated by this
seat rather than assumed, is in §2.2.

**Real people are using it and talking back, and the tracker emptied while this
seat was not looking.** Twelve issues have now arrived from the in-app feedback
widget ([#4](https://github.com/pumasi-ai/pumasi-sign/issues/4)–[#15](https://github.com/pumasi-ai/pumasi-sign/issues/15)).
**Read on the tracker by this evaluation at 02:00 UTC: exactly one is open.**

**Four closed between the fifth evaluation and this one, and none of them was
closed by this role.** [#7](https://github.com/pumasi-ai/pumasi-sign/issues/7)
and [#8](https://github.com/pumasi-ai/pumasi-sign/issues/8) — both
`accepted` · `priority: high`, both of which this file has carried as *live to
a user* through three evaluations — were closed **2026-09-01 at 00:59:11 and
00:59:12 UTC**; [#13](https://github.com/pumasi-ai/pumasi-sign/issues/13) at
01:01:19 and [#14](https://github.com/pumasi-ai/pumasi-sign/issues/14) at
01:02:24, `state_reason: completed`, all four by the GitHub account `pumasiAI`.
**Each closure trails a Cloudflare deployment by seconds** (§2.2), which is the
first time in this product's record that an issue was closed *by a deploy*
rather than by a merge. #7 and #8 are correctly closed — this evaluation
verified both against the live host rather than against the tracker (§2.2).

**One open issue, and it is this evaluation's whole triage.**
[#15](https://github.com/pumasi-ai/pumasi-sign/issues/15) — *"[Feedback] 🐛
Bug: this is a test one."* — filed **2026-09-01 01:21:39 UTC** from
`https://sign.pumasi.ai/dashboard` by `Pumasi Admin <admin@pumasi.ai>`, Chrome
151 on Windows, `America/Chicago`. The body is its own verdict: it reports no
defect and describes itself as a test. Labelled **`rejected`** by this
evaluation with the ground cited on the issue, and it is **not** a backlog
entry.

**It is nevertheless evidence, and about something other than a bug.** It was
filed **nineteen minutes after** the deployment at 01:02 UTC, from a signed-in
browser session on the deployed product, in the same timezone from which the
four issue closures were made. Recorded under **Q-012** as a fact about when a
human was in the live product, with no claim about who; see §2.5.

**And one standing observation survives the clear-down.** #6, #10 and #11 were
three reports about how `/login` looks on a phone, which is why `BACKLOG.md`
batched them as one packet rather than three. That packet shipped
(`bbde48f`, `1d2743f`), and the three defects are gone from the tracker and
from the live bundle. The observation that produced it stands: **the login page
is where this product meets a stranger on a phone**, and a quarter of every
report this product has ever received has been about how it looks there.

**Surface A is live.** `https://pumasi.ai/products/pumasi-sign/` → 200
(`pumasi-web` `content/products/pumasi-sign.md`).

**`roadmap/MARKET.md` now exists**, with both comparators' pricing read from
their own pages on 2026-08-31 and dated. The first publication of this file
listed its absence as a gap; it is closed.

---

## 2 · Why not `beta`

`beta` in the role file's own table means **strangers can rely on it, known
gaps are listed here, and data survives**. **Six** verified facts say not yet.
**Three of the six changed character at this evaluation and none of them
went away.** §2.2 stopped being a defect list and became the record of an
unannounced deployment; §2.3 went from *"none of these claims has ever been
public"* to *"one of them is public and untrue"*; and §2.6 split, one half
reaching users and the other not. **A `beta` claim needs strangers to be able
to rely on the product. Strangers can now see it — that is what changed — and
the first thing this product tells them about its licence is false.**
Each is a `BACKLOG.md` entry; the order below is not the backlog's — the
backlog orders by what to build next, this orders by what is furthest from
`beta`.

### 2.1 · Both gates now cover the served tree; what they run there is 28 tests across five files, and the breadth that is left is named

This is still the one that matters most, and at this evaluation, for the first
time in four, **it moved** — `2471a29` added seven assertions and a fifth file,
and one of them drives `service/src/worker.ts`, which no test in this
repository had ever touched. That is breadth gained, not merely a defect
closed, and it is the only figure on this page that improved for a reason other
than the deployment.

**Correction, carried from the fourth evaluation and left standing.** Through
the third evaluation this section's heading read *"what they run there is
**two tests wide**"*, and its body said *"What the new job runs is two tests,
and they test one file."* **Both were true when written and both are now
false.** Two deliveries retired them — coder job `0046` (`spec/0004`,
`auth-session.test.ts`) and coder job `0050` (`spec/0005`,
`envelope-lifecycle.test.ts`) — and this file had not caught up. A register
that argues from a measurement its own delivery retired is the failure this
page exists to prevent, so it is named rather than quietly overwritten.

**Re-run by the sixth evaluation at `2471a29` on 2026-09-01 at 02:03 and
02:05 UTC**, per §0 rider (a) — locally, by this seat, not read off a job
report or a packet, and with the number of runs behind each figure stated
because "I ran it" without a count is what rider (b) exists to stop:

```
$ npm test          # = pumasi/tools/gate.sh step 1, repository root
Test Files  6 passed (6)                                           # 2 runs
     Tests  85 passed (85)                                         # 2 runs
# pass 28                                                          # 2 runs
# fail 0                                                           # 2 runs
assert-service-suite-ran: 28 passing, 0 failing, from 5 compiled   # 2 runs
```

**Runs behind each figure.** Root `npm test` was run **twice**, both runs read
in full, both identical. **No determinism claim is made from two runs** —
rider (b) asks for 40, this evaluation did not run 40, and that remains the gap
the fourth evaluation named and no evaluation since has closed.

**21 across four files → 28 across five, and that is this section's finding.**
The added file is `service/src/test/envelope-expiry.test.ts` (**A-410–A-416**),
and the assertion worth naming on its own is **A-415**, which drives
`service/src/worker.ts` — the entrypoint and router, previously covered by
nothing. Three consecutive evaluations recorded a release that closed a defect
and widened no coverage; this one records the reverse. The frontend half is
unchanged at 85/6.

**One caution attaches to the number and it is the same one as always.** The
28 are assertions on the served tree, and the served tree is not the *served
build*: every one of them passes at `2471a29`, and `2471a29` is not deployed
(§2.6(ii)). A green suite here has never been evidence about production and is
not now — that is Q-018's default part (c), restated because this is the first
evaluation at which the two trees are a full release apart in the *other*
direction.

**What closed.** `sign.pumasi.ai` is served by the Cloudflare Worker in
`service/`, not by the FastAPI app in `backend/`. `.github/workflows/ci.yaml`
now defines four jobs — `backend` (`:10`), `frontend` (`:60`), **`service`
(`:104`)** and `e2e` (`:144`) — and the `service` job builds before it tests
(`dist/` is `.gitignore`d) and then runs
`.github/scripts/assert-service-suite-ran.sh` against the suite's own reported
counts, independently of the build step. **Its ability to fail was proven on
real runs, not argued**: run
[33419949879](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33419949879)
turns `service` red on a broken test while the other three jobs stay green, and
run [33419950651](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33419950651)
turns it red on an unbuilt tree — the exit-0-having-run-nothing trap.

**What closed since the last evaluation.** The merge gate runs it too.
`pumasi/tools/gate.sh:25` is still `if npm test; then echo "   tests: PASS"`,
but this repository's root `package.json` `test` script is now
`npm run test:frontend && npm run test:service`, and the service half installs,
builds and runs the worker's suite through the same guard `ci.yaml` uses.
Measured by running it at `d18d534`, not by reading it (§0 rider (a)).
`BACKLOG.md`'s old item 2, delivered at `d18d534`.

**What did not close, and is now the sharper half.** Three things:

**(i) The gate is still one command an author runs by hand.**
`GET /repos/pumasi-ai/pumasi-sign/branches/main/protection` returns **404
"Branch not protected"**, re-measured this tick. CI reports and blocks nothing.
So between a change and `main` there is exactly one check and the author of the
change is the only one who ever runs it. That is **Q-025** in full, it is
untouched by `d18d534`, and its entry stays open — what `d18d534` fixed was the
narrower complaint that the check excluded production.

**(ii) What the new job runs is 21 tests across four files — no longer two
against one pure function, and the remaining gap is breadth.** All four files
in `service/src/test/` were **read** for this evaluation rather than counted,
and they fall into two distinct halves:

- **Two of them now drive the real Durable Object.** `auth-session.test.ts`
  (A-300–A-308, job `0046`) and `envelope-lifecycle.test.ts` (A-400–A-409, job
  `0050`) both import `newHarness` from `./support/durable-harness.js`, and
  A-300 is explicitly *"the harness constructs the real Durable Object: whole
  schema, migrations, routing"*. This is a different **kind** of coverage from
  what this page recorded twice, not more of the same: it exercises routes,
  the SQLite schema and the session cookie. **The old sentence "`durable.ts` …
  covered by nothing" is withdrawn** — sessions and the envelope surface are
  covered.
- **The Q-018 boundary was honoured, and that is worth recording.** A-302 is
  named *"establishSession admits a verified email at any domain — recorded,
  not endorsed (Q-018)"*. The suite characterizes the divergence without
  adjudicating it, which is exactly what `BACKLOG.md` demanded of the packet.
  Nothing here decides which tree is the product.

**One sentence from the old text survives verbatim, re-checked at `f7c8d03`,
and it should not be lost in the good news:**

- **`e2e-workflow.test.ts` is still not an end-to-end test of anything.** Its
  imports are `node:test`, `node:assert/strict`, `pdf-lib` and
  `stampAndCertifyPdf` — **identical to `stamping.test.ts`** — and it calls no
  route, starts no worker and touches no store. The file *name* over-states
  what it does. **The number still escapes this page**: `# pass 21` is printed
  by the merge gate and will be quoted in release notes, and a reader who sees
  a file called `e2e-workflow` in a suite of four will over-read it exactly as
  `# pass 2` invited. Renaming it is a five-minute honesty fix and is named in
  `BACKLOG.md` item 2.
- Those two stamper tests still assert **shape, not content**: stamped bytes
  longer than the original, page count 2, two 64-hex-character hashes, and
  `notEqual(originalHash, completedHash)` — which passes for *any* mutation.
  Neither asserts that a signer's name, a date or a checkbox value reached the
  page. Unchanged, and unaddressed by either new file.
- **Still covered by nothing**, re-checked: `worker.ts`, `storage/r2.ts`,
  `mail.ts`, `feedback.ts`, `convert/graph.ts`; and inside `durable.ts` —
  envelope creation, correction and copy, templates, admin, every file route,
  `finalize`'s stamping branch, and **the OAuth callback**, which is where
  `BACKLOG.md` item 2's named first slice sits.

**And the coverage found defects, which is the point of having it — and one of
them is already repaired because of it.** The lifecycle suite characterized
three unguarded envelope transitions — `cancel` with no status guard at all,
`complete` missing `completed`, `decline` missing all three — which became
`BACKLOG.md` item 1 and were **fixed at `68e5d08`** (retired there; still
undeployed, §2.6(i)); and a customer-set `expires_at` that the worker never
acts on (A-409), now `BACKLOG.md` **item 1**. That is a suite doing its job
within hours of existing, finding a defect that was then fixed inside a day,
and it is the strongest argument on this page for finishing the breadth.

**(iii) The one suite that exercises routes drives the wrong server.**
`frontend/playwright.config.ts` boots `uvicorn` locally, or in CI a Docker
image built from the root `Dockerfile` — **`backend/`**, both times. So the six
e2e specs assert that a FastAPI server signs users in. §2.2 is the proof that
this is not theoretical: **CI run 33430138500 is green on all four jobs at
`d18d534` while the deployed sign-in button still returns a 404**, and `e2e` is
green precisely *because* it drives the tree where that route exists. Nothing
in the current four jobs could go red on that defect — including the two that
`d18d534` added to the gate, since neither touches routing. This is L-006 and L-009 in a
single artefact, and it is the sharpest thing on this page.

The three suites and the gate, recounted at `d18d534` — one cell changed, and
it is the last column of the last row:

| Tree | Tests | Run by CI | Run by the merge gate |
| :--- | ---: | :--- | :--- |
| `backend/` | 541 test functions (545 collected in CI) | yes | no |
| `frontend/` unit | **85 in 6 files** (was 69 in 5; `spec/0003` added 9 frozen cases) | yes | **yes** |
| `frontend/` e2e — **drives `backend/`** | 6 Playwright specs in 4 files | yes | no |
| **`service/` — the deployment** | **21 in 4 files** (was 2 in 2; `spec/0004` added 9, `spec/0005` added 10) — 19 against the real Durable Object, 2 on `core/stamping.ts` | **yes, since `ef851d6`** | **yes, since `d18d534`** |

This remains [L-006](https://github.com/pumasi-ai/governance/blob/main/lessons/L-006-tests-that-cannot-fail.md)
at suite scale and [L-009](https://github.com/pumasi-ai/governance/blob/main/lessons/L-009-two-paths-one-claim.md)
in a second product, and **Q-018 is open exactly as it was** — parts (a), (b)
and (c) of its *default* are taken; *which tree is the product* is untouched.
The claim this page may now make is wider than it was and is still made
narrowly: **CI exercises the deployed tree's PDF stamper, its session and
sign-in path, and its envelope lifecycle — and nothing else about it.** Not
`worker.ts`, not R2, not mail, not feedback, not conversion, not the OAuth
callback, and no route through a real HTTP server. No claim here about
production is read off the `backend` or `e2e` jobs, and none is.

**What this does *not* buy, stated before someone reads a promotion into it.**
The number moved because two packets wrote tests, not because the product got
more reliable — and the tests' first act was to **find two defects that are
still unfixed** (`BACKLOG.md` items 1 and 2). Rider (c) forbids promoting on
evidence strength alone, and this is evidence strength alone. The rung does
not move.

### 2.2 · Both `priority: high` entry-path defects are **closed, deployed and verified live** — and this is where the deployment is dated

**This subsection stops being a reason not to promote and becomes the record of
how the reason ended.** It is kept rather than deleted because the deployment
it describes is undated everywhere else, and three other subsections cite it.

#### What is deployed, established rather than assumed

Nothing in the queue announced this deploy, so the build had to be identified
from the artefact. Measured by this seat, 2026-09-01 01:57–02:02 UTC:

```console
$ curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'
/assets/index-CnoFAC2c.js                     # was /assets/index-j38Qwibz.js
```

```console
$ cd service && npx wrangler deployments list | tail
Created:     2026-09-01T01:02:16.876Z
Author:      atxapplellc@gmail.com
Source:      Unknown (deployment)
Version(s):  (100%) 96ff7004-45f0-439d-a4e0-68e35f739462

$ npx wrangler versions view 96ff7004-45f0-439d-a4e0-68e35f739462
Created:     2026-09-01T01:02:16.132Z
Author:      atxapplellc@gmail.com
Handlers:    fetch
```

**Four deployments in sixteen minutes** — 00:46:02, 00:58:51, 01:01:10 and
**01:02:16 UTC**, the last of which is what serves users now. Source
`Unknown (deployment)`, i.e. a `wrangler deploy` from a workstation, not CI:
this repository's `ci.yaml` has no deploy job.

**Which commit it was built from, by chunk fingerprint rather than by
timestamp.** The served `SendView-CSp0J5J6.js` contains `Sign a document`,
`Review & sign` and `Envelope sent for signature!` and does **not** contain
`signers_json` or `Draft saved — send it whenever` — so it is **after**
`1338f68`. The served `SignedOutView-C2J9s3yp.js` carries
`pa-6 text-center pumasi-card border rounded-lg shadow-sm` and the 44px
`logo-mark.png`, which `0e26917` introduced and `1338f68` does not have — so it
is **at or after `0e26917`**. And `Handlers: fetch` alone, with no `scheduled`,
puts it **before `2471a29`**, which added that export and an hourly cron
trigger. **The deployed tree is `0e26917`** — equivalently `ba1cea7`, whose only
change is `README.md`. The deploy at **01:02:16.132 UTC** precedes that
commit's own timestamp (**01:02:21 UTC**) by five seconds, so it was built from
a working tree, not from a pushed commit.

**One of job `0064`'s four readings does not survive re-measurement, and it is
the dating one.** That entry concluded *"'Sign a Document' (`1338f68`, #13) is
absent from the deployed dashboard chunk, so it landed before 01:01 UTC."*
`1338f68` touches **`SendView.vue` only** (`git show --stat`), and the string
`Sign a Document` does not occur anywhere in `frontend/src` at any commit —
`git grep -n "Sign a Document" -- frontend/src` is empty. The absence was real
and meant nothing. The deploy is **after** `1338f68`, not before it. Its other
three readings — the bundle hash, the landing route, the `alpha` constant — all
re-measured clean below and in §2.3.

#### The two defects

- **[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) — "sign in again"
  errors. Closed 2026-09-01 00:59:12 UTC, and this seat verified the repair on
  the live host rather than on the tracker.** The served
  `SignedOutView-C2J9s3yp.js` computes its button target by calling the main
  bundle's exported helper with `"/"`, and that helper is

  ```js
  function ml(e){return`/login?next=`+encodeURIComponent(e)}
  ```

  — so *Sign in again* now points at `/login?next=%2F`, which answers
  **`200 text/html`**. **Decisively, the helper `d18d534` deleted is gone from
  the shipped JavaScript**: `grep -c '/api/auth/login?next=' index-CnoFAC2c.js`
  returns **0**, against the two-function pair the fifth evaluation extracted
  from `index-j38Qwibz.js`. `GET /api/auth/login?next=%2F` still answers `404`,
  and nothing targets it any more. **§5's state (iii) is now empty.**

- **[#8](https://github.com/pumasi-ai/pumasi-sign/issues/8) — the app root has
  no product page in production. Closed 2026-09-01 00:59:11 UTC; the page is
  live.** Route table extracted from the shipped bundle by this seat, first
  entry:

  ```js
  {path:`/`,name:`landing`,component:()=>Wl(()=>import(`./LandingView-C5khdw3s.js`),__vite__mapDeps([0,1,2,3])),meta:{public:!0}}
  ```

  `/` is the landing page, `meta.public`, and `LandingView-C5khdw3s.js` fetches
  **200, 10 046 bytes**. Five case-insensitive `landing` matches now occur in
  the main bundle against **zero** at every previous evaluation. `LandingView.vue`
  has reached users. **`BACKLOG.md` B1 and B2 are both retired by this
  deployment** — B2 wholly, B1 **only in its (d) half.** Its (b) half, the
  licence, was never done and shipped false. That is §2.3.2, and it is the one
  row on this page that the deployment made worse.

### 2.3 · The public page made three claims the repository could not back. Two were repaired before it shipped. **The third shipped.**

**This is the most serious section on this page and the only one the
deployment made worse.** Through five evaluations this section could end with
*none of these has ever been public*. That sentence is now false in the one
place it mattered: the page went live at 2026-09-01 01:02 UTC (§2.2) carrying
two corrected claims and one uncorrected one.

1. **`BETA` → `ALPHA` — fixed at `a49f594`, and it shipped fixed.**
   `frontend/src/stage.ts` exports `STAGE = "alpha"` as the one constant, with
   `STAGE_LABEL` and `STAGE_BADGE` derived by expression. **Verified in the
   served chunk**, which opens

   ```js
   var g=`alpha`,_=g.charAt(0).toUpperCase()+g.slice(1),v=`${g.toUpperCase()} — ACTIVE DEVELOPMENT`
   ```

   so the banner a stranger reads is `ALPHA — ACTIVE DEVELOPMENT` and the
   sentence beneath it is *"Pumasi Sign is in active Alpha"*. `STAGE_PLAYBOOK.md`
   Stage 1 asks Surface B for a *"prominent `[ALPHA - ACTIVE DEVELOPMENT]`
   stage badge"*; that is what deployed. **No user has ever seen a `BETA`
   badge on this product.** Frozen case **A-001** fails the build if this
   file's `**Current stage:**` line and that constant move apart — L-007 closed
   by a gate rather than by a copy nobody checks, and this deployment is the
   first evidence that the gate was worth having.

2. **"Apache-2.0 (Open Source)" — not fixed, and it is now published.** This is
   `pumasi/DECISIONS.md` **Q-021**, open, its named default unclaimed, and
   **its central premise is overtaken.** That entry rests on *"Not yet public:
   the page is on `main` and undeployed … which is the whole reason this is a
   question and not an incident."*

   **The three claims, extracted from the chunk a stranger's browser downloads,
   at 2026-09-01 01:57 UTC:**

   ```js
   o(` Zero Per-Seat Fees • Unmetered Envelopes • 100% Apache-2.0 `,-1)
   d(`span`,null,`Pumasi Sign is in active `+t(u(_))+` — Unmetered PDF stamping & SHA-256 audit certificates under Apache-2.0.`,1)
   d(`td`,{class:`font-weight-medium`},`License & Source Code`),
   d(`td`,{class:`text-center font-weight-bold text-primary`},`Apache-2.0 (Open Source)`),
   d(`td`,{class:`text-center text-medium-emphasis`},`Proprietary Closed Source`),
   d(`td`,{class:`text-center text-medium-emphasis`},`Proprietary Closed Source`)
   ```

   And, re-measured at `2471a29`:

   ```console
   $ ls LICENSE*
   ls: cannot access 'LICENSE*': No such file or directory
   $ gh repo view pumasi-ai/pumasi-sign --json licenseInfo,visibility
   {"licenseInfo":null,"visibility":"PUBLIC"}
   ```

   **This seat's reading, stated plainly because the packet that ordered this
   evaluation asked for it and because a register that hedges here is not
   evidence: yes — this is a live public misstatement.** Not an unbacked
   marketing adjective and not a stale roadmap line. It is a **licence claim**,
   made in the third column of a table whose other two columns say
   *"Proprietary Closed Source"*, on a public repository that grants no rights
   at all. The comparison is the point of the row: it invites a reader to
   choose this product **because** its terms differ from the incumbents', and
   the terms it names do not exist. A reader who forks this repository on the
   strength of that row has no licence to do so.

   **Three corrections to how this has been recorded, none of which softens
   it.** *(a)* Job `0064` reported the chunk *"contains the string
   `Apache-2.0 (Open Source)` three times"*. That string occurs **once**.
   `Apache-2.0` occurs three times, in **three different claims** — the hero
   strip, the stage banner and the table row, quoted above. The count was right
   and the attribution was wrong, and the true shape is worse: three
   independent assertions, not one repeated. *(b)* Those three are **exactly**
   the list frozen case **A-005** pins byte-identical to `10a523d`, which the
   coder seat wrote as a scope guard with the note *"RETIRE THIS CASE WITH
   Q-021"*. The frozen case and the deployed bundle agree, so nothing drifted;
   what changed is only that the strings left the repository. *(c)* This file
   has said since its first publication that the remedy is the steward's. That
   is unchanged. **This seat did not add a `LICENSE`, did not remove a claim,
   and did not edit `LandingView.vue`** — Q-021's two named answers are exactly
   those two acts, and taking either would answer a steward question by
   performing it.

   **What changed about the question, and it is a change of kind.** Q-021 was
   raised as *a question and not an incident* on the express ground that the
   claim was not public. It is public. Evidence recorded on that entry, and on
   **Q-028**, whose entanglement resolved itself by shipping rather than by
   anyone answering it.

3. **Uncited competitor pricing — fixed at `a49f594`, and it shipped fixed.**
   **Verified in the served chunk**: the table's figures are `$0 (Unmetered)`,
   `$11 / mo (Personal)`, `$30 – $45 / user / mo (Standard, Business Pro)`,
   `$10 – $12 / sender / mo (Light)` and `$30 – $36 / mo for 3 senders
   (Business)`, and the caption beneath them reads *"Competitor **pricing and
   limits** above are as published on each vendor's own pricing page, read
   **2026-08-31**"*, linking DocuSign's and SignWell's own pricing pages and
   [`MARKET.md`](MARKET.md), and closing *"Prices move; the date is part of the
   claim."* Frozen cases **A-003** and **A-004** parse those figures out of
   `MARKET.md` at test time, so neither can fork from the file it checks.
   **This is the one thing on the page that is public and true because a
   process caught it in time**, and it is worth setting beside item 2: the same
   `a49f594` fixed two of three claims, and the third was left because it was
   the steward's — and then the page shipped anyway.

### 2.4 · "Data survives" is not established, and one open entry contemplates dropping it

`beta` promises data survival. Real accounts, sessions and signed documents
live in the worker's Durable Object SQLite store and its R2 bucket. There is no
backup, restore or retention evidence in this repository to cite, and Q-018's
named alternative — FastAPI on Railway is the product — states in terms that
under that branch the worker's data "must be migrated or knowingly dropped".
A stage label cannot promise survival while a live decision entry lists
dropping it as an option the steward may still take. **§2.1 sharpens this
rather than softening it:** the store in question is `durable.ts`, which no
test touches.

Separately, `beta` is the rung at which **PR-2** binds (`PRODUCT-RULES.md`
v1.0, read fresh this packet from `pumasi` branch `worktree-product-rules`
`0115758` — it is still **not** on `pumasi` main, which is **Q-017**, and
absence from main is not compliance; that entry has now been flagged by five
consecutive evaluations and remains open). PR-2 is satisfied in substance here:
three kinds (bug / enhancement / question), landing as public GitHub issues
labelled `feedback`, URL parameters matching
`token|state|code|session|secret|key|auth|password` redacted before they leave
(`service/src/feedback.ts:32`), errors as message + location, optional contact,
and the composed report shown before send. **One divergence, re-checked at
`ef851d6` and unchanged**, and it is the privacy-shaped one: opening the dialog
sets a fallback canvas as the attachment immediately
(`FeedbackDialog.vue:185`–`188`) and then replaces it asynchronously with a
real `html2canvas(document.body)` capture (`:193`–`:197`). The user presses
nothing. PR-2 says *"a screenshot travels only when the user attaches one"*. In
an e-signature product the page being captured is somebody's contract, which is
CHARTER §5.2's *never the user's own material*. The user can see it and remove
it (`:201`), so it is opt-out and informed — but opt-out is not what the rule
says, and this must be closed before any `beta` promotion. `BACKLOG.md` **item 4**
(renumbered from item 5 in the fifth reorder).

**PR-1** binds *always*, at every stage, and is **still not met** — though the
gap has narrowed and the narrowing should be recorded rather than left to look
like inaction. A root `package.json` now exists (authored under `spec/0001` so
that `gate.sh` step 1 has something to run). It carries **no `version` field**,
deliberately and self-documentedly, to avoid taking a backlog item inside a
packet scoped to something else. So: `frontend/package.json` reads `0.0.0`
while `service/package.json` reads `0.1.0` (two hand-maintained copies, L-007),
no version is visible to a user anywhere in the SPA, there is no `/version`
endpoint, and `FeedbackDialog.vue::buildContext` (`:105`–`:122`) carries
thirteen fields and **not the version it concerns**. Every one of the **seven** open
issues is therefore a defect report without a version — re-counted on the
tracker by the fifth evaluation. `BACKLOG.md` **item 5** (renumbered from item
6 in the fifth reorder). **Its cost rose at `d18d534`:** the root
`package.json` was edited there and its `version` field deliberately left
absent, pinned by frozen case **A-208** (`spec/0003/SPEC.md:211`) so that no
later packet takes this item in passing — so the packet that does take it must
retire or amend A-208 in the same commit.

### 2.5 · A merged fix reaches users at no defined time — and this evaluation is the first to record the *other* failure mode of that

Nothing in this project owns deployment: **Q-012** is open and explicitly
outside CHARTER Part 0's proceed-on-default rule, `CHARTER §2.1`'s flow ends at
a published release note, and no role file names deploying as a duty. **At the
first five evaluations the cost of that was always the same shape: merged work
not reaching users.** At this one the cost arrived from the opposite direction
and it is worse.

**A deploy happened, and the queue learned about it by measuring the artefact.**
Four deployments between 00:46 and 01:02 UTC on 2026-09-01 (§2.2), no release
note, no digest entry, no `DECISIONS.md` line, and no job in
`pumasi-ops/jobs/done/` claiming any of them. Job `0064` — a **marketing** seat,
working on `README.md` — found it by re-`curl`ing a bundle filename, said so,
and correctly refused to edit this register. The undeployed backlog this
section has tracked since first publication went from four commits to zero
without anyone recording that it had.

**Both directions of Q-012's gap are now on the record, and they are one gap.**
An unowned duty does not mean *the thing never happens*; it means **nobody knows
when it happens**. Merged-and-unshipped is what that looked like for five
evaluations. Shipped-and-unannounced is what it looks like now, and it is the
more dangerous half, because the register kept saying `NOT MET`, *"never
public"* and *"still live to a user"* about a product where all three had
stopped being true — and would have gone on saying it. **Q-021's premise
expired the same way.** Evidence recorded on **Q-012**, with what is measurable
about the actor and nothing about who they are.

**What the deployment did settle, and it should be said, because this section
spent five evaluations arguing for it.** The four merged repairs this file has
carried as costs — #7's sign-in path, #8's landing page, the envelope guards,
and the login-page presentation batch — are all live. **Q-028's entanglement
resolved itself by shipping.** That entry predicted the exact artefact: *"the
only build that carries #7's repair also publishes 'Apache-2.0 (Open Source)'"*.
It did, in one `frontend/dist`, exactly as written — and neither of the two
questions it named was answered first. An entry whose forecast is confirmed by
the event it was raised to prevent has been vindicated in the least useful way
available.

### 2.6 · A deadline the served tree ignores — repaired in source at `2471a29`, deployed nowhere. And an executed agreement it let be un-executed — repaired **and now deployed**

**Both halves were found by the lifecycle suite `spec/0005` added. At this
evaluation they finally part company: one reached users and one did not.**

**(i) Three envelope transitions were unguarded — repaired at `68e5d08`, and
this is the evaluation at which it reached a user.** `cancel` ran
`UPDATE submissions SET status = 'cancelled'` with **no status check at all**
and audited the event; `decline` carried **none** of `complete`'s three guards,
so a signer who had already signed could decline, a `completed` envelope
flipped to `declined`, and the sender was emailed that their executed agreement
had been refused; and `complete` guarded `cancelled` and `declined` but omitted
`completed`. All three refuse — 409, 410, 409 — before reading the request
body, behind one predicate (`isTerminal`, `durable.ts:114`). `2471a29` also
added `expired` to that predicate, so the same three guards now cover a fifth
terminal status with no fourth guard written.

**Four sets of line numbers now exist for these three guards and three of them
are wrong — measured, not assumed.** Re-read at `2471a29` by this seat with
`grep -n isTerminal service/src/durable.ts` and the enclosing route confirmed
for each: **`cancel` 409 at `:1383`**, **`complete` 410 at `:1591`**,
**`decline` 409 at `:1652`**. Q-031 cites `:1239`/`:1434`/`:1490`; the fifth
evaluation cites `:1252`/`:1452`/`:1513`; **and job `0065`'s digest entry,
written at this same commit, cites `:1367`/`:1575`/`:1636`** — sixteen lines
short of each, in the entry whose stated purpose was to spare the next reader
exactly this. None of the three locates a guard in the tree that exists today.
Recorded because it is the fourth consecutive time a line citation into
`durable.ts` has been stale within hours of being written, which is an argument
about the practice and not about any of the four seats: **a line number into
this file is not a durable citation, and a predicate name is.**

**This section carried a sentence that the repair disproved, and it is struck
rather than deleted.** It read: *"`complete` … omits `completed`, which mostly
yields the wrong refusal rather than a wrong write."* **False.** The completion
count reads `AND is_cc = 0`, so a **CC recipient** is still `pending` when the
envelope completes, passes both guards, re-enters `finalize()` and writes a
second `completed` audit event — re-stamping the executed PDF where one is
present. A reachable wrong write. `spec/0006/SPEC.md` §S1a carries the
reasoning; frozen case **A-406** is the measurement.

**And it is no longer true on `sign.pumasi.ai`.** The deployment of 01:02 UTC
was built from `0e26917`, of which `68e5d08` is an ancestor
(`git merge-base --is-ancestor 68e5d08 0e26917`), and `wrangler.jsonc` ships
the worker and `frontend/dist` as one artefact. **§5's state (iii) — *fixed in
source, still wrong in production* — is empty for the first time since this
file defined it.** Q-031's own Status line, which says the three transitions
*"still behave the old way for anyone using the live service"*, is now stale in
the good direction; that is the steward's entry and this seat has not edited
it. **This is not a promotion ground**: it removes a `beta` blocker, it does
not supply `beta` evidence.

**What this did and did not falsify, because the distinction decided the
remedy.** [`VALUE.md`](VALUE.md) **C1** — *a cryptographic record of what was
signed* — is **not** falsified and was not: the stamped PDF and its certificate
live in R2 and a status overwrite never touched them. What was damaged was
narrower: the Durable Object row and the audit log came to say `cancelled`
about an envelope whose certificate says `completed`. One product, two records,
one claim — **L-009** at row scale. Neither route was reachable through the
product's own UI, which is what made the repair a plain defect rather than a
capability removal; that was never a reason to leave them open.

**(ii) `expires_at` did nothing — repaired at `2471a29`, and the live worker
does not have it.** The repair is real and this seat verified it in the tree
rather than taking the job's report: `service/wrangler.jsonc` now carries
`"crons": ["0 * * * *"]`, `worker.ts` exports `scheduled`, the sweep flips
past-deadline `pending` envelopes to `expired` with one system-authored audit
row each, the token surface refuses an expired envelope (landing view
`expired`, `request-code` `410`, `complete` `410`), and seven new frozen cases
**A-410–A-416** drive it — one of which, **A-415**, is the first assertion in
this repository to exercise `service/src/worker.ts`.

**And none of it is deployed.** The live worker's version metadata, read by
this seat at 02:00 UTC:

```console
$ npx wrangler versions view 96ff7004-45f0-439d-a4e0-68e35f739462
Handlers:            fetch
Compatibility Date:  2026-08-01
```

**`fetch` alone.** A worker carrying `2471a29` would list `fetch, scheduled`.
`POST /api/jobs/daily` answers `404`, and `/__internal/expire` is not probeable
from outside — any `POST` to a non-`/api/` path returns `405` from the ASSETS
binding, which is what a nonsense path returns too, so that probe proves
nothing in either direction. The handler list does.

**So on `sign.pumasi.ai` right now**, the Send wizard still collects a deadline
(`SendView.vue:865`), still refuses a past date (*"The expiration date must be
in the future."*), still tells the sender **"Without an expiration date, the
envelope stays open until completed or voided."** — and a recipient holding a
token link can still sign an envelope months past that date. **This is §5's
state (iii)'s new and only occupant**, and it arrived on the same day the state
emptied. **Q-035**, the can-hurt window on that release, is open and closes
2026-09-07.

**Why this is still a `beta` blocker.** The product's whole value proposition
is a tamper-evident record. (i) is now sound for every user; (ii) is sound in
the repository and false to every user; and the thing standing between them is
**Q-012**, which is not a build entry and not this seat's. `BACKLOG.md` retires
item 1 as built and does **not** claim it as delivered.

### On #9, which is *not* a reason

[#9](https://github.com/pumasi-ai/pumasi-sign/issues/9) ("login and signup
failure", `priority: high` when the first evaluation opened) was the strongest
single argument against any promotion. It did not survive contact with the
evidence: coder job `0018` established against the live host that the worker
**cannot emit a `403` at all** (every status it returns was grepped), that its
`establishSession` (`service/src/durable.ts:655`) has no domain gate, and that
the reporter's exact wording occurs once in the fleet — in `pumasi-booking`.
#9 is closed as not this product's defect. It is recorded here rather than
dropped, because a stage file that quietly loses its own strongest
counter-argument is not evidence. **Note the boundary carefully**: #9 being
another product's defect did *not* mean this product's sign-in path was
healthy, and §2.2 has now found a real 404 on it.

---

## 3 · What `beta` requires

In the order that reduces the distance fastest. Each maps to a `BACKLOG.md`
entry; this list is the *gate*, the backlog is the *schedule*, and the two are
deliberately not in the same order. **Two lines are struck at this evaluation
and one is new; the count did not go down.**

1. ~~**The envelope lifecycle made trustworthy**~~ — **built at `68e5d08` and
   delivered to users by the deployment of 2026-09-01 01:02 UTC.** Verified by
   ancestry against the dated build (§2.2, §2.6(i)). **Struck.**
2. ~~**#7's fix delivered to a user**~~ — **delivered by the same deployment**,
   verified on the live bundle rather than inferred (§2.2). Issue closed
   00:59:12 UTC. **Struck.**
3. **The licence claim made true, or removed — and it is now urgent in a way it
   has never been.** *New at this evaluation, and it replaces the old line 5.*
   Surface B is live; one of its three claims is a licence grant this
   repository does not make (§2.3.2). This is the only line in this list that
   is **worse** than it was at the last evaluation, and it is the only one no
   agent may close: **Q-021**, open, named default unclaimed. `BACKLOG.md`
   **B1**, which retains only its (b) half.
4. **`expires_at` honoured for a user** — built at `2471a29` and **not
   deployed** (§2.6(ii)). The repository keeps the promise; the product does
   not. What is left is a **deploy** (**Q-012**), which this line now shares
   with nothing else — it is the entire undeployed set.
5. **More than a PDF stamper for the gates to run** (`BACKLOG.md` **item 2**,
   Q-018, Q-025). **Moved at this evaluation for the first time in four:**
   28 assertions across five files, and `worker.ts` is covered (§2.1). What is
   left is R2, mail, feedback, conversion and the OAuth callback, and the fact
   that the `e2e` suite — the only one that drives routes over HTTP — still
   drives `backend/` rather than the worker.
6. **PR-2's screenshot made opt-in** (item 3).
7. **PR-1 met** — one version, user-visible, in every feedback report (item 4).
   Re-checked at `2471a29`: root `package.json` still has no `version` field,
   `/api/version` answers **404**, and no version string occurs in the served
   bundle. A stranger cannot tell which build they are using; issue #15
   arrived from the live product carrying none.
8. **Data survival evidenced** — a stated retention and backup posture for the
   Durable Object store and R2, citable from this file (item 17).
9. **A real end-to-end user completing a send-and-sign without an engineer**,
   which is `STAGE_PLAYBOOK.md`'s Stage-2 exit gate and is the thing all of the
   above only make measurable.

**Two of nine struck in one tick, and the stage did not move.** That is the
honest arithmetic and it deserves a sentence rather than an apology: lines 1
and 2 were both *"a merged repair has not reached a user"*, which is a defect
in the delivery pipeline, not evidence about the product. Removing them changes
what this product owes; it does not change what anyone can rely on. Line 3 is
new and is a claim to strangers that is untrue, which is precisely the kind of
thing the `beta` rung is about.

---

## 4 · Known gaps, carried openly

- **"Apache-2.0 (Open Source)" is served to the public from a repository with
  no `LICENSE`.** *New wording at this evaluation; the gap is not new, its
  status is.* Three distinct claims on the live landing page (§2.3.2), against
  `licenseInfo: null` on a `PUBLIC` repository. **Q-021**, open, named default
  unclaimed, and its own *"not yet public"* premise expired at 01:02 UTC on
  2026-09-01. This is the most serious gap on this page.
- **A deploy of a hosted product happened with no release note and no entry
  naming the actor.** Four of them, 00:46–01:02 UTC (§2.2, §2.5). **Q-012**,
  open. What is measurable is on that entry; who did it is not this seat's to
  assert.
- Two backends, one product; the `e2e` suite — the only one that drives routes
  over HTTP — drives the tree users do **not** reach (§2.1, Q-018, Q-025).
  **Changed at `2471a29`:** the deployed tree's own suite is **28 across five
  files** and `worker.ts` is no longer uncovered. What is left is R2, mail,
  feedback, conversion and the OAuth callback.
- **A customer-set `expires_at` is honoured on `main` and ignored by every
  user's product** (§2.6(ii), Q-035, Q-012). The live worker's handler list is
  `fetch` alone. This is now the whole of the undeployed set.
- **A settings-only PATCH silently deletes the sender's message to signers, on
  the live product and on `main`.** *New at this evaluation, and it is the
  top of `BACKLOG.md`.* The deployed `EnvelopeDetailView` chunk sends
  `{expires_at, reminders_enabled, reminder_interval_days}` and no `message`;
  the deployed worker writes `message = body.message != null ? … : null`, so
  the omission is a delete, while `title` is preserved by `?? sub.title` on the
  adjacent line. The dialog then reports *"Envelope settings updated."* Found
  by coder job `0065` and handed up rather than folded in; verified here
  against the served artefact, not only the source.
- `main` is **not a protected branch**; CI reports and blocks nothing (§2.1).
- No version number (PR-1, §3 line 7). Re-checked at `2471a29`: root
  `package.json` still carries no `version` field, deliberately, and frozen
  case A-208 asserts the absence — see `BACKLOG.md` **item 4**.
- **`PRODUCT-RULES.md` is not on `pumasi` main** and the product-manager role
  file requires reading it every packet. Checked at `pumasi` @ `cdc0b9a`:
  `ls PRODUCT-RULES.md` → *No such file or directory*; it exists only at
  `0115758` on the unmerged branch `worktree-product-rules`, from which it was
  read this pass (v1.0, PR-1 and PR-2 unchanged). **Q-017**, open, flagged by
  **eight** consecutive evaluations. Not this product's defect and not this
  seat's to close; recorded because both PR-1 and PR-2 gaps above are ranked
  against a register that `main` does not contain.
- **No `RISK_ZONES.yaml`** — confirmed absent at `2471a29`. CHARTER **Part 4**
  says the risk classification *"lives in `RISK_ZONES.yaml` in each
  repository"*. **The absence fails safe** — Part 4 defaults an unmapped path
  to *can hurt someone* — and it has now been applied by hand twice, by job
  `0058` for Q-031 and job `0065` for Q-035, each seat reasoning it out
  independently. `BACKLOG.md` **item 6**.
- **`catalog.json` still says `seed`.** Re-read directly at `pumasi` @
  `cdc0b9a` by this evaluation: `products[]` says `"status": "seed"` for both
  products, `items[]` uses `status` for `pumasi-sign` and `maturity` for
  `pumasi-booking`, `pumasi-tunnel` is absent from both, and top-level
  `updated` still reads `2026-08-29`. Unchanged through six evaluations.
  **Q-019**, open. Not editable by any seat today.
- **Closed at this evaluation, and named rather than dropped:** `README.md`
  described the product as one FastAPI service on Railway; job `0064` corrected
  it at `ba1cea7` and this file's gap list no longer carries it.
- **Closed earlier:** `roadmap/MARKET.md` did not exist and now does;
  competitor numbers in product code were uncited, now cite it, and **now ship
  cited** (§2.3.3).

---

## 5 · What this file now contradicts, and who fixes each

A stage set on evidence disagrees with files that were written before it
existed. Naming them is this file's job; editing them is not.

**What the sixth evaluation changed here, and it is nearly everything.** Every
row in this table rested on one shared fact — *the live host has never moved* —
and that fact expired at 2026-09-01 01:02 UTC. **All seven rows were
re-measured by this seat between 01:56 and 02:06 UTC; not one was carried.**
Four retire, one moves in the bad direction, one is new, and one is unchanged.

**The four states, unchanged as definitions.** A claim can be **(i)** wrong in
source and in production, **(ii)** right in both, **(iii)** fixed in source and
still wrong in production, or **(iv)** merged and never shipped — present on
`main`, absent from every deployment there has ever been.

| Says | Where | State | Owner of the fix |
| :--- | :--- | :--- | :--- |
| *Sign in again* → `{"error":"Endpoint not found"}` | was live on `sign.pumasi.ai`; fixed at `d18d534` | **RETIRED — (ii) right in both.** Re-measured 01:58 UTC, on the artefact and not the tracker: the served `SignedOutView` chunk targets `/login?next=%2F`, which answers **`200 text/html`**, and `grep -c '/api/auth/login?next=' index-CnoFAC2c.js` returns **0** — the helper `d18d534` deleted is gone from the shipped JavaScript, where the fifth evaluation found it still present. Issue [#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) closed 00:59:12 UTC. | **Nobody. Done and delivered.** `BACKLOG.md` **B2** retired. |
| A `completed`, `declined` or `cancelled` envelope can be voided, re-completed or declined again | was live on `sign.pumasi.ai`; fixed at `68e5d08` | **RETIRED — (ii) right in both.** `68e5d08` is an ancestor of `0e26917`, the commit the deployed build was fingerprinted to (§2.2), and `wrangler.jsonc` ships worker and `frontend/dist` as one artefact. Guards re-read at `2471a29` behind `isTerminal` (`durable.ts:114`): `cancel` 409 `:1383`, `complete` 410 `:1591`, `decline` 409 `:1652`. **`pumasi/DECISIONS.md` Q-031's Status line — *"the three transitions still behave the old way for anyone using the live service"* — is now stale in the good direction.** That is the steward's entry; this seat did not edit it. | **Nobody. Done and delivered.** Q-031's 7-day window still closes 2026-09-07. |
| `expired` is *"past its optional `expires_at` deadline — **flipped by the daily job**"* | `CLAUDE.md:107`–`:110` | **(iii) Fixed in source, still wrong in production — and it is this state's only occupant.** `2471a29` added `"triggers": {"crons": ["0 * * * *"]}` to `service/wrangler.jsonc` and a `scheduled` export to `worker.ts:189`. The live worker does not have it: `wrangler versions view 96ff7004-…` reports **`Handlers: fetch`**, read by this seat at 02:00 UTC. **A second, smaller defect in the same sentence survives the repair**: the job is **hourly**, not daily, so `CLAUDE.md`'s wording is now wrong in a new way even about the tree that has it. | **A coder, for the wording** — one word, and it is the whole of what is left in source; job `0065` measured it, correctly declined to edit `CLAUDE.md` from a `service/` packet, and handed it here. **For the behaviour a user meets, a deploy** — **Q-012**. `BACKLOG.md` item 1 is retired as built; the deploy is not a build entry. |
| `BETA` chip and "in active Beta" | `frontend/src/views/LandingView.vue` | **RETIRED — (ii) right in both, and the badge now reads `ALPHA`.** The served landing chunk opens ``var g=`alpha` `` and derives `ALPHA — ACTIVE DEVELOPMENT` from it. Two evaluations disputed this row's state while it was unshipped; the deployment settled it, and it settled it correctly, because `a49f594` had already made the badge a function of **this file**. Frozen case **A-001** keeps them together. | **Nobody. Done and delivered**, and it is the one thing the unannounced deploy got right by construction rather than by luck. |
| "Apache-2.0 (Open Source)", "100% Apache-2.0", "…certificates under Apache-2.0." | `LandingView.vue:43`, `:80`, `:210` — **and now `https://sign.pumasi.ai/`** | **(i) Wrong in source and in production. Was (iv); the deployment moved it, and this is the only row on this page that got worse.** Three distinct claims, extracted from the served chunk at 01:57 UTC and quoted in full in §2.3.2, against `ls LICENSE*` → nothing and `gh repo view --json licenseInfo` → `null` on a `PUBLIC` repository. **This seat's reading: a live public misstatement.** The table row sets it against *"Proprietary Closed Source"* for both named competitors, so it is an invitation to choose this product on terms that do not exist. | **The steward, via Q-021**, whose *"not yet public"* premise expired at 01:02 UTC. **No agent may settle it either way** — its default is to add `LICENSE`, an outward grant CHARTER Part 0 does not release; its alternative is to strike the copy, which is the same decision taken by deleting the evidence. `BACKLOG.md` **B1**, reduced to its (b) half. Evidence added to Q-021 and Q-028 by this evaluation; neither closed. |
| Uncited competitor pricing | `LandingView.vue` comparison table | **RETIRED — (ii) right in both.** Fixed at `a49f594` and shipped fixed: the served caption reads *"as published on each vendor's own pricing page, read **2026-08-31**"*, links both vendors and [`MARKET.md`](MARKET.md), and closes *"Prices move; the date is part of the claim."* Frozen cases **A-003**/**A-004** parse the figures out of `MARKET.md` at test time. | **Nobody. Done and delivered.** The role file's *"every claim about a competitor is cited or absent"* is now satisfied on a public page and not only in a repository. |
| `"status": "seed"` | `pumasi/catalog.json` | **Unchanged, and it is the one row here that six evaluations have not moved.** Re-read directly at `pumasi` @ `cdc0b9a` by this seat: `products[]` says `seed` for both products, `items[]` uses `status` for `pumasi-sign` and `maturity` for `pumasi-booking`, `pumasi-tunnel` is absent from both, and top-level `updated` still reads **`2026-08-29`** — three days stale across a tick in which this product deployed its own front page. Details below. | **Nobody, today** — **Q-019**, open, and its default is a *role-file amendment* nobody has made. Not editable by this seat and not edited here. |
| A settings-only PATCH deletes the sender's message to signers | `durable.ts` PATCH `/api/submissions/{id}`; `EnvelopeDetailView.vue` settings dialog | **(i) Wrong in source and in production — NEW ROW, and it is the new top of `BACKLOG.md`.** The served `EnvelopeDetailView-C4VlFBtA.js` sends `{expires_at, reminders_enabled, reminder_interval_days}` and then toasts *"Envelope settings updated."*; the worker writes `message = body.message != null ? … : null` while preserving `title` with `?? sub.title` on the line above. Omission is deletion. Introduced once, at `c2b674e`, and unchanged since — so it is in the deployed build and on `main` alike. Found by coder job `0065` through its harness and handed up; **verified here against the served chunk as well as the source.** | **A coder**, `BACKLOG.md` **item 1**. Not blocked on any open window. |

**State (iii) emptied and refilled on the same day, and that is the shape of
this evaluation.** It held two occupants for five evaluations — #7's sign-in
path and the envelope guards — and both were emptied by one deployment at
01:02 UTC. It acquired its new and only occupant at `2471a29`, thirty-six
minutes later, when a coder merged the `expires_at` sweep into a repository
that had just been deployed from. **The pipeline did not get faster; the queue
and the deployer are simply not synchronised, which is Q-012 stated as a
mechanism rather than as a complaint.**

**Why state (iv) is now empty, and what that costs.** Every claim on
`LandingView.vue` was in (iv) at the last evaluation — *"merged and never
shipped"*, a state in which a false claim harms nobody. **The category is
empty because the page shipped**, and its one untrue claim moved to (i)
rather than being fixed on the way out. **The distinction this table drew at
the fifth evaluation — that (iv) means *publish the page for the first time*,
which cannot happen before Q-021 answers — was correct and was overtaken by an
act.** It is kept here, struck rather than deleted, because the reasoning was
sound and the outcome is the argument for taking such reasoning seriously
before the deploy rather than after.

**`catalog.json`, read directly and recorded rather than edited** (Q-019 is
open; no seat may edit that file today, and this seat's `May Write` does not
include it). Both arrays were re-read by this evaluation at `pumasi` @
`cdc0b9a`, and every cell is unchanged from the fifth evaluation's reading at
`3bc1822` and the fourth's at `133d337`:

| Array | `pumasi-sign` | `pumasi-booking` | `pumasi-tunnel` |
| :--- | :--- | :--- | :--- |
| `products[]` | `"status": "seed"` | `"status": "seed"` | **absent** |
| `items[]` | `"status": "seed"` | `"maturity": "seed"` — **different key** | **absent** |

Three things follow, and the third is the one nobody had written down:

- Both arrays record `seed` for this product against **`alpha`** in this file.
  `seed` is not a rung on the role file's ladder at all, and nothing states how
  the two vocabularies map. The file's top-level `updated` still reads
  `2026-08-29` — **three days stale, across a tick in which this product
  deployed its front page.**
- `pumasi-tunnel` is absent from **both** arrays, though it serves live public
  surfaces. That is Q-019's opening fact and it is unchanged.
- **The two arrays disagree with each other on the field name**, and that is
  why two seats reported different things and neither was wrong.
  `items[]` uses `status` for `pumasi-sign` and `maturity` for
  `pumasi-booking` — adjacent entries, same concept, two keys. Recorded for
  whoever answers Q-019: the file is not merely stale, it is internally
  inconsistent, and any owner assigned to it inherits a schema question as well
  as a content one.

**The commons product card is now wrong, and it is the one downstream file this
evaluation was asked to flag rather than fix.**
`pumasi-web/content/products/pumasi-sign.md` reproduces the Stage 1 row as
**"IN PROGRESS — Surface A live, Surface B undeployed"**. Surface B is live.
The fifth evaluation flagged this forward in exactly these words — *"If B1 or
B2 ever deploys, that page and this file move together"* — and B1's deploy half
has now happened. **`pumasi-web` is not this seat's to edit**; the correction
belongs to a marketing packet, and it must be taken **after** this file, not
before, or the card becomes the more current of the two and the fork runs the
wrong way (**L-007**).

**And one instruction attaches to that packet, stated here because this is the
file it will read.** The card **must not** begin claiming Apache-2.0 on the
ground that the live page now does. **Q-021 is open, the repository has no
`LICENSE`, and a second surface repeating an untrue licence grant is how one
mistake becomes a pattern.** The card should say what is true: the stage is
`alpha`, Surface B is live, and the licence is an open question on the
steward's desk.

---

## Change log

| Date | Stage | Why |
| :--- | :--- | :--- |
| 2026-08-31 | `alpha` (first publication) | Live, in real use, feedback answered — but the green gate covers a tree no user reaches (2 tests on the deployed one, none in CI), two `priority: high` defects sit on the entry path, the root page is undeployed, and public copy claims a licence the repository does not carry. `beta` means strangers can rely on it and data survives; neither is evidenced. |
| 2026-08-31 | `alpha` (**unchanged** — second evaluation, at `ef851d6`) | One of the four reasons above moved and three did not. **Moved:** CI now runs the deployed tree, and its ability to fail was proven on real runs. **Did not move:** what that job runs is two tests on one file, and the *merge* gate runs none of them on a branch with no protection (§2.1); #7 is still open and is now **diagnosed** as a live `404` on the sign-in path, caused by the SPA calling a route only `backend/` has (§2.2); Surface B is still undeployed, re-measured on the same bundle filename as before (§2.2); and there is still no `LICENSE`. Determinism measured for the first time on this product — **40/40 and 40/40 on the two suites that could run, 0 runs on the two that could not** (§0 rider (b)). No promotion: Stage 1's exit gate needs both landing surfaces live and one is not, so **`STAGE_PLAYBOOK.md` Event 3 did not fire**. No demotion: nothing regressed, and rider (c) forbids demoting for evidence strength alone. |
| 2026-08-31 | `alpha` (**unchanged** — third evaluation, at `d18d534`) | Two of the reasons below moved, one correction was made to this file, and the rung did not change. **Moved:** the *merge* gate now runs the served tree — root `npm test` at `d18d534` reports `Test Files 6 (6)`, `Tests 85 (85)`, `# pass 2`, `# fail 0`, where before it reported 5/69 and zero service assertions — and #7's raw `404` is fixed in source. **Did not move:** what either gate runs on the served tree is still two tests on one file (now `BACKLOG.md` **item 1**, promoted to the top of the backlog for exactly that reason); `main` is still unprotected (404, re-checked); Surface B is still undeployed; there is still no `LICENSE`. **Corrected:** §5 filed the `BETA` chip as *fixed in source, live in production* — the second half was false. The page carrying it has never been deployed (route table extracted from the live bundle: no `landing` route, `/` is the dashboard), so it is **merged, never shipped**, and the remedy is the page's *first* deploy, which Q-021 gates. **§5's genuine state (iii) is #7**: live in production, fixed on `main`, undeployed — the first time this product has had one. Determinism re-measured for the suite that exists *today*, because `d18d534` changed its shape: **40 of 40**, identical counts every run (§0 rider (b)). No promotion: Stage 1's exit gate still needs both landing surfaces live and one is not, so **`STAGE_PLAYBOOK.md` Event 3 did not fire**. No demotion: nothing regressed. **New:** #7's fix and the unbacked Apache-2.0 claim can only ship in the same bundle — raised as **Q-028**. |
| 2026-08-31 | `alpha` (**unchanged** — fourth evaluation, at `f7c8d03`) | **The main event is a correction to this file's own central number.** §2.1's heading and body argued from **2** — *"what they run there is two tests wide"*, *"two tests, and they test one file"* — and `VALUE.md` §4 repeated it. Two deliveries had retired that: `spec/0004` (job `0046`, `auth-session.test.ts`) and `spec/0005` (job `0050`, `envelope-lifecycle.test.ts`). **Re-run by this seat at `f7c8d03` on 2026-08-31 22:22 UTC: `Test Files 6 (6)`, `Tests 85 (85)`, `# pass 21`, `# fail 0`, `21 passing, 0 failing, from 4 compiled`.** 21 across four files, two of which drive a real Durable Object through `test/support/durable-harness.ts`. §2.1, §0 rider (a), §1, §3, §4 and `VALUE.md` §4 all corrected in this commit; `BACKLOG.md`'s item 1 carried the same stale number and was corrected there. **Withdrawn as false:** *"both assertions are against one file"* and *"`durable.ts` … covered by nothing"*. **Kept, re-checked, and still true:** `e2e-workflow.test.ts` is still not an end-to-end test of anything — same four imports as `stamping.test.ts`, no route, no worker, no store. **New — §2.6, and it is why this is not a promotion.** The coverage went and found two defects on the served tree, both unfixed and both now the top of `BACKLOG.md`: three envelope transitions with missing or absent status guards (`durable.ts:1240`, `:1434`, `:1490` — an executed agreement can be voided or declined after the fact), and a customer-set `expires_at` the worker never acts on (no `scheduled` export, no cron trigger; A-409). `VALUE.md` C1 is **not** falsified by either — the stamped PDF and its certificate are untouched — and this file says so rather than overstating. **Feedback is not quiet this tick:** #10 and #11 arrived from the live product at a 384x691 mobile viewport since the last evaluation and were triaged `accepted` · `priority: normal`; §1 records what three login-page reports out of eight say. **Corrected about this page's own evidence:** rider (b)'s 40/40 was measured against a suite shape that no longer exists, and **this evaluation ran the current command once, not 40 times** — recorded as 1 of 1 with no determinism claim, and named as a gap. Rider (a)'s table and §5's live-host rows now mark which evidence was re-run here and which is **inherited**; this seat did not `curl` the deployment. **§5 gained a row:** `CLAUDE.md`'s *"flipped by the daily job"* is wrong in source and in production. **`catalog.json` re-read at `pumasi` @ `133d337` and unchanged.** No promotion: Stage 1's exit gate still needs both landing surfaces live and one is not, so **`STAGE_PLAYBOOK.md` Event 3 did not fire** — and §2.6 is new evidence against, not for. No demotion: nothing regressed; the two defects were always there and are newly *visible*, which rider (c) forbids demoting for. |
| 2026-09-01 | `alpha` (**unchanged** — fifth evaluation, at `56a8bf8`) | **The main event is that half of §2.6 was delivered and the stage did not move, which is the distinction this page exists to hold.** Coder job `0058` merged `68e5d08`: the three unguarded envelope transitions now refuse — `cancel` `409` (`durable.ts:1252`), `complete` `410` (`:1452`), `decline` `409` (`:1513`), one predicate `isTerminal` at `:109`, each guard the first statement of its branch so a refusal writes and audits nothing. **Verified in the tree at `56a8bf8` by this seat**, not read off `pumasi/DECISIONS.md` **Q-031**, whose cited line numbers are the pre-fix ones. **No promotion, and the reasons are separable.** (a) **Merged is not shipped:** re-`curl`ed at 2026-09-01 00:29 UTC, the deployed bundle is unchanged (`/assets/index-j38Qwibz.js`) and `GET /api/auth/login?next=%2F` is still `404`, so all three transitions still behave the old way for every user — the repair moved from §5 state (i) to state (iii), which is a claim about the repository, not the product. **State (iii) now has two occupants** (#7 and this) and per **Q-028** they wait on the same single bundle. (b) **The release widened no coverage:** re-run at `56a8bf8`, `Test Files 6 (6)`, `Tests 85 (85)`, `# pass 21`, `# fail 0`, `21 passing, 0 failing, from 4 compiled` — **identical to `f7c8d03`**. Runs behind each: service assertions **4 runs**, the guard line **3 runs**, the frontend figures **2 runs read**. A defect closed is not breadth gained, and rider (c) forbids promoting on evidence strength. (c) **Stage 1's exit gate still needs both landing surfaces live and one is not**, so **`STAGE_PLAYBOOK.md` Event 3 did not fire**; **Q-024** is open fleet-wide and no gate figure is quoted from here into anything public. **No demotion:** nothing regressed. **Corrected:** §2.6 carried *"`complete` … omits `completed`, which mostly yields the wrong refusal rather than a wrong write"* — **false**, disproved by the work it described. The completion count reads `AND is_cc = 0`, so a CC recipient is still `pending` at completion, passes both guards, re-enters `finalize()` and writes a second `completed` event, re-stamping the executed PDF. `spec/0006/SPEC.md` §S1a has the reasoning, frozen case **A-406** the measurement. Struck here and retired with the same correction in `BACKLOG.md`. **Not claimed:** `VALUE.md` C1 was not falsified — the stamped PDF and its certificate live in R2 and a status overwrite never touched them; the damage was the row and the audit log disagreeing with the certificate, **L-009** at row scale. **New in §4:** this repository has **no `RISK_ZONES.yaml`**, which forced `0058` to apply CHARTER Part 4 by hand to classify Q-031 — ranked `BACKLOG.md` **item 7**, not higher, because Part 4's own default (*unmapped → can hurt someone*) already fails safe. **Which tree this file's stage is a claim about is now stated in the header** (**Q-018**): the Worker in `service/` and the SPA it serves, not `backend/`. **Re-verified rather than carried:** the live host (re-`curl`ed), `catalog.json` at `pumasi` @ `3bc1822`, `PRODUCT-RULES.md` still absent from `pumasi` main (**Q-017**, seventh consecutive evaluation), the `expires_at` grep, `e2e-workflow.test.ts`'s four imports, and the undeployed set re-counted at **four** commits of which **two** change what a user meets. **Still not closed:** rider (b) asks for 40 runs and this evaluation ran 4; recorded as a gap, not papered over. |
| 2026-09-01 | `alpha` (**unchanged** — sixth evaluation, at `2471a29`) | **The main event is that `sign.pumasi.ai` was deployed and nobody in the queue announced it.** Four deployments between 00:46 and 01:02 UTC, `Source: Unknown (deployment)`, the live one being version `96ff7004-45f0-439d-a4e0-68e35f739462` at **01:02:16.132 UTC** — five seconds before commit `0e26917`'s own timestamp, so it was built from a working tree rather than a pushed commit. Dated by chunk fingerprint, not by clock: the served `SendView` chunk is post-`1338f68`, the served `SignedOutView` chunk matches `0e26917`, and `wrangler versions view` reports `Handlers: fetch` alone, which puts it before `2471a29`. **Four merged repairs reached users at once** — #7's sign-in path, #8's landing page, `68e5d08`'s envelope guards, and the login-page presentation batch — and **§5's state (iii) emptied**, for the first time since this file defined it. **No promotion, and the reasons are separable.** (a) **Stage 1's exit gate now reads met on its literal words and is recorded `NOT MET` anyway**, because Stage 1 asks Surface B for *honest* calibration and the page that shipped carries three claims that Apache-2.0 governs this code, on a repository whose `licenseInfo` is `null`. The unmet half changed from *Surface B is not live* to *Surface B is live and one of its claims is untrue*; what flips it is **Q-021**, not a build. **`STAGE_PLAYBOOK.md` Event 3 therefore did not fire and must not** — firing it would put a second Pumasi surface behind the same unbacked claim. (b) **Four repairs delivered is not evidence, it is the removal of four gaps**; coverage, data survival, PR-1 and the licence are all where they were. (c) **Q-024** is open fleet-wide and no gate figure is quoted from here into anything public. **No demotion**, and this is the closest call this file has had: the product acquired a live public misstatement, which is a real regression in what a stranger is told. It is not a *stage* regression — `alpha` already means *do not rely on it* and the ladder has no rung below that this product has outgrown — and rider (c) forbids moving the rung for a defect that a named steward question already owns. **§5 re-measured in full, not carried: five of seven rows moved.** Four retire — the sign-in 404, the envelope transitions, the `BETA` chip (which shipped reading **`ALPHA`**, derived from this file, exactly as `a49f594` designed), and the uncited competitor pricing (which shipped **cited**, dated 2026-08-31, linking both vendors and `MARKET.md`). **One got worse and is the reason this pass exists:** *"Apache-2.0 (Open Source)"* moved from state (iv) *merged and never shipped* to state **(i)** *wrong in source and in production*. **One is new:** a settings-only `PATCH` deletes the sender's message to signers, live in both trees, now `BACKLOG.md` **item 1**. **State (iii) refilled the same day it emptied**, with `2471a29`'s `expires_at` sweep, which is built and undeployed. **Coverage moved for the first time in four evaluations:** root `npm test` at `2471a29`, run twice by this seat at 02:03 and 02:05 UTC, `# pass 28`, `# fail 0`, `28 passing, 0 failing, from 5 compiled` — 21/four → **28/five**, and **A-415 is the first assertion in this repository to drive `service/src/worker.ts`**. **Corrections made to other seats' readings, all re-measured rather than inherited:** job `0064` dated the deploy *before* `1338f68` from a string that occurs nowhere in `frontend/src` — it is after; job `0064` reported *"`Apache-2.0 (Open Source)` three times"* — that string occurs once and `Apache-2.0` occurs three times in three **different** claims, which is worse; and job `0065`'s digest cites the three envelope guards at `:1367`/`:1575`/`:1636` where they are at **`:1383`**, **`:1591`**, **`:1652`** — the fourth stale `durable.ts` citation in four days, which is an argument about the practice and not about any seat. **Evidence added to `pumasi/DECISIONS.md` Q-021, Q-028 and Q-012; none closed, no deadline set, no default softened, and no `LICENSE` added or removed.** **Re-verified rather than carried:** the live host in full (bundle, route table, landing/`SendView`/`SignedOutView`/`EnvelopeDetailView`/`LoginView` chunks, the stylesheet, the deployment list and the handler list), `catalog.json` at `pumasi` @ `cdc0b9a` (still `seed`, still `updated: 2026-08-29`), `PRODUCT-RULES.md` still absent from `pumasi` main (**Q-017**, **eighth** consecutive evaluation), and PR-1 still unmet with its first observed cost — issue #15 arrived from the live product with thirteen diagnostic fields and no version, and there is no way for its reporter to have supplied one. **Still not closed:** rider (b) asks for 40 runs and this evaluation ran 2. |
