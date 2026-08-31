# STAGE — Pumasi Sign

**Current stage:** `alpha`
**Set:** 2026-08-31, first publication of this file, at `5cb3bf8`.
**Re-evaluated:** 2026-08-31 (**third evaluation**), at `d18d534`. **Stage
unchanged** — not promoted, not demoted. Evidence re-derived below, not carried.
**Stage 1 exit gate:** **NOT MET**, and the reading has **not** changed —
Surface B (the product's own root landing page) is built and undeployed.
Re-derived at `d18d534` by extracting the *deployed route table*, which is a
stronger negative than the string count the last evaluation ran: the shipped
bundle's routes include `dashboard` and **not** `landing`, so `/` in production
is the dashboard and `LandingView.vue` has never reached a user (§2.2).
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

**This file said that chip was also "live in production", and that was wrong.**
The marketing manager that finished job `0038` measured it on 2026-08-31 at
18:49 UTC and did not edit this register, correctly, because it is this seat's.
This evaluation re-measured it independently and confirms the correction: the
chip lives in `LandingView.vue`, and **`LandingView.vue` has never been
deployed** — the shipped bundle has no `landing` route at all (§2.2). So the
chip is **merged, never shipped**, not *fixed in source and still wrong in
production*. The distinction is not pedantry: it changes the remedy from *the
deploy of a correction* to *the first deploy of the page*, and it means every
other claim on that page — including the Apache-2.0 lines this repository
cannot support while **Q-021** is open — is equally unshipped. §5 carries the
corrected row.

**§5's third state is not empty, though: it has an example it did not have when
it was written.** Issue #7's raw `404` on the sign-in path is *live in
production*, its fix is *merged* at `d18d534`, and nothing has deployed. That
is a live defect whose correction sits on `main` — the genuine (iii), measured
in §5.

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

What this evaluation adds is the other half of the rider — **who and when** —
for every claim below. **Nothing in this table is carried from the second
evaluation**; every row was re-run at `d18d534` by this seat, on 2026-08-31
between 20:05 and 20:40 UTC.

| Evidence | Who re-ran it | When |
| :--- | :--- | :--- |
| CI run 33430138500 (`main` @ `d18d534`, four jobs) | this evaluation, via `gh run view` | 2026-08-31 |
| Branch protection on `main` (404 *"Branch not protected"*) | this evaluation, via `gh api` | 2026-08-31 |
| Root `npm test` (= `gate.sh` step 1, **new shape**), 40 consecutive runs | this evaluation, locally at `d18d534` | 2026-08-31 |
| Live host: bundle filename, bundle **contents and route table**, `/api/auth/login`, `/login`, `/api/health` | this evaluation, via `curl` | 2026-08-31 |
| `SignedOutView.vue` / `utils/http.ts` / root `package.json` source claims | this evaluation, reading the tree at `d18d534` | 2026-08-31 |
| `gap-*` class inertness, `service/src/test/` contents, absence of a root `version` | this evaluation, reading the tree at `d18d534` | 2026-08-31 |
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
rather than a copy of it (L-007). Run by this evaluation at `d18d534`:

```
Test Files  6 passed (6) · Tests  85 passed (85)
# pass 2 · # fail 0
assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled
```

**What that does and does not buy, stated so the next reader does not
over-read it.** `GATE: PASS` on this repository now carries a number about the
tree that answers `sign.pumasi.ai`, where before it carried none. The number is
**2**, and both assertions are against one file, the PDF stamper. And the gate
is still one command a coder runs by hand: `GET
/repos/pumasi-ai/pumasi-sign/branches/main/protection` → **404 "Branch not
protected"**, re-checked this tick, so CI reports and blocks nothing. Q-025's
question — *is `GATE: PASS` an agent's own report?* — is untouched and its
entry stays open. What closed is the narrower complaint that the report
excluded production. `BACKLOG.md` **item 1** is what is left.

### Rider (b) — measure determinism, do not inherit a single green run

**The figure this product carried was taken against a different suite, so it
was not inherited — it was re-measured.** `d18d534` changed *which tree the
root suite runs*: before it, `npm test` was the frontend half only; after it,
the same command also installs, builds and runs `service/`. The second
evaluation's 40/40 therefore says nothing about the command that exists today,
and this evaluation ran the new one from scratch.

Raw counts, and the number of runs actually performed:

| Suite | Runs | Result | Per-run counts |
| :--- | ---: | :--- | :--- |
| Root `npm test` at `d18d534` — **what `gate.sh` step 1 executes, in its new shape** | **40** | **40 pass, 0 fail** | **identical on every run**: `Test Files 6 passed (6)`, `Tests 85 passed (85)`, `# pass 2`, `# fail 0`, `assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled` |
| `backend/` pytest — 541 test functions | **0** | **not run, not inherited** | — |
| `frontend/` Playwright e2e — 6 specs | **0** | **not run, not inherited** | — |

**One command, not two, and that is the point of the change.** The second
evaluation reported two figures because the frontend suite and the service
suite were reached by different commands and only one of them was the gate.
They are now one command, so one row is the honest shape: each of the 40 runs
executed both halves, and the `service` half was `npm ci` → `npm run build` →
`node --test dist/test/*.test.js` → guard, from scratch, every time. Exact
command:

```
for i in $(seq 1 40); do npm test; done   # from the repository root, at d18d534
```

**40 of 40 passed, and no run varied in any reported count** — not exit status
only, and not 40 runs of a subset.

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

**The figure is stronger than a pass rate, and deliberately so.**
Each of the 40 runs was checked for its **reported assertion counts**, not only
its exit status. `service`'s `test` script is `node --test dist/test/*.test.js`
against a `.gitignore`d `dist/`, and an unbuilt tree exits **0** having run
nothing (L-006; frozen case `spec/0002` A-103 pins exactly this). A pass rate
of 40/40 would have been satisfiable by 40 runs of nothing. **All 40 reported
`# pass 2` and all 40 reported the guard's line**
(`2 passing, 0 failing, from 2 compiled file(s) for 2 source file(s)`), which
is the check that the build actually happened inside each run.

**Context, not a claim about the fleet:** `pumasi-booking` measured 40 of 40
(job `0030`) and `pumasi-tunnel` reported 3 failures in 40 (**Q-024**, whose
own record has since been complicated by a port-collision finding — not this
product's business, and cited only so the comparison is not read as settled).
40 of 40 on the gate command here is a good answer on the one suite that could
run; it says nothing about the 541 nobody re-ran, and **it is not a coverage
claim** — a deterministic suite of two tests is deterministic and two tests
wide, which is `BACKLOG.md` item 1.

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

Measured 2026-08-31 against `main` @ `d18d534` and against the live host, by
running the commands rather than by reading the claim. Provenance per §0.

**CI is green on `main`, and it covers the tree users meet.** Run
[33430138500](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33430138500)
at `d18d534`: `backend` ✓, `frontend` ✓, **`service` ✓**, `e2e` ✓. **The
qualification that attaches to this sentence is the whole of §2.1, and it has
not gone away**: those four green jobs sit over a defect that is live in
production right now (§2.2).

**The merge gate now runs the served tree, and that is new since the last
evaluation.** Root `npm test` at `d18d534`, run by this evaluation:
`Test Files 6 passed (6)`, `Tests 85 passed (85)`, `# pass 2`, `# fail 0`,
`assert-service-suite-ran: 2 passing, 0 failing, from 2 compiled`. Before
`d18d534` the same command reported 5 files / 69 tests and **zero** service
assertions. `BACKLOG.md`'s old item 2, delivered by coder job `0037`; §0 rider
(a) records what it does and does not buy.

**The product is live and answers.** `GET https://sign.pumasi.ai/api/health`
→ `200 {"status":"ok","service":"pumasi-sign",…}`.

**Real people are using it and talking back.** Six issues arrived from the
in-app feedback widget between 2026-08-30 22:29 and 2026-08-31 14:47
([#4](https://github.com/pumasi-ai/pumasi-sign/issues/4)–[#9](https://github.com/pumasi-ai/pumasi-sign/issues/9));
**five remain open and all five carry a cited verdict** (#9 closed as another
product's defect — see §2.5). **No new issue has arrived since the last
evaluation** — re-checked this tick, and there are no open unlabelled issues —
so this evaluation's feedback intake is *quiet* and adds no verdict. **#7 stays
open on purpose although its fix is merged**: the person who reported it still
meets the bug (§5). That is the `alpha` sentence exactly: it works for people who talk to
the builders, and it breaks in front of them.

**Surface A is live.** `https://pumasi.ai/products/pumasi-sign/` → 200
(`pumasi-web` `content/products/pumasi-sign.md`).

**`roadmap/MARKET.md` now exists**, with both comparators' pricing read from
their own pages on 2026-08-31 and dated. The first publication of this file
listed its absence as a gap; it is closed.

---

## 2 · Why not `beta`

`beta` in the role file's own table means **strangers can rely on it, known
gaps are listed here, and data survives**. Five verified facts say not yet.
Each is a `BACKLOG.md` entry; the order below is not the backlog's — the
backlog orders by what to build next, this orders by what is furthest from
`beta`.

### 2.1 · Both gates now cover the served tree; what they run there is two tests wide

This is still the one that matters most, and it has moved again — the half that
was open at the last evaluation is closed, and what is left is the narrowest
and hardest part.

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

**(ii) What the new job runs is two tests, and they test one file.** Both
files in `service/src/test/` were **read in full** for this evaluation rather
than counted. They have identical import lists — `node:test`,
`node:assert/strict`, `pdf-lib`, and `stampAndCertifyPdf` from
`../core/stamping.js` — and nothing else. Three consequences:

- **`e2e-workflow.test.ts` is not an end-to-end test of anything.** It calls no
  route, starts no worker and touches no store; it is a second scenario against
  the same pure function. The file *name* over-states the coverage, and the
  first publication of this file's table row (`service/` | 2) let that pass.
  **The number now escapes this page**: `# pass 2` is printed by the merge gate
  and quoted in the release note, so the over-reading is available to every
  future reader of a `GATE: PASS`. That is why this is `BACKLOG.md` **item 1**
  as of this evaluation, and no longer item 4.
- Both assert **shape, not content**: stamped bytes longer than the original,
  page count 2, two 64-hex-character hashes, and
  `notEqual(originalHash, completedHash)` — which passes for *any* mutation.
  Neither asserts that a signer's name, a date or a checkbox value reached the
  page.
- **Covered by nothing:** `durable.ts` (sessions, envelopes, signing, the whole
  API surface — including the `establishSession` domain-gate divergence Q-018
  flags), `worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`.

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
| **`service/` — the deployment** | **2, both on `core/stamping.ts`** | **yes, since `ef851d6`** | **yes, since `d18d534`** |

This remains [L-006](https://github.com/pumasi-ai/governance/blob/main/lessons/L-006-tests-that-cannot-fail.md)
at suite scale and [L-009](https://github.com/pumasi-ai/governance/blob/main/lessons/L-009-two-paths-one-claim.md)
in a second product, and **Q-018 is open exactly as it was** — parts (a), (b)
and (c) of its *default* are taken; *which tree is the product* is untouched.
The claim this page may now make is narrow and is made narrowly: **CI exercises
the deployed tree's PDF stamper and nothing else about it.** No claim here
about production is read off the `backend` or `e2e` jobs, and none is.

### 2.2 · Two open `priority: high` defects on the entry path — both now fixed or absent in source, and **both still live to a user**

- **[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) — "sign in again"
  errors. Diagnosed at the last evaluation, fixed in source at `d18d534`, and
  **still live**.** The repair is real and this evaluation verified it in the
  tree rather than taking the job's report: `SignedOutView.vue:2` imports
  `loginPageUrl`, `:6` sets `const signInUrl = loginPageUrl("/")`,
  `utils/http.ts:44` returns `"/login?next=" + encodeURIComponent(next)`, and
  `loginRedirectUrl` has no definition and no caller anywhere in the tracked
  tree. The page it targets answers on the deployment:
  `GET https://sign.pumasi.ai/login?next=%2F` → **200 `text/html`**.

  **And none of that has reached anyone.** Measured against the live host on
  2026-08-31 at 20:10–20:12 UTC:

  ```
  $ curl -s https://sign.pumasi.ai/ | grep -o '/assets/index-[^"]*\.js'
  /assets/index-j38Qwibz.js
  $ curl -s -i 'https://sign.pumasi.ai/api/auth/login?next=%2F'
  HTTP/2 404
  {"error":"Endpoint not found"}
  ```

  The bundle filename is the same one the previous two evaluations fetched. The
  **decisive** measurement is not the filename, though — it is that the shipped
  JavaScript still contains the function `d18d534` deleted:

  ```js
  function pl(e){return`/api/auth/login?next=`+encodeURIComponent(e)}
  function ml(e){return`/login?next=`+encodeURIComponent(e)}
  ```

  `pl` is the minified `loginRedirectUrl`. The removed code is still shipping.
  **This is §5's genuine state (iii)** — a live defect whose fix is merged and
  undeployed — and it is the first one this product has had. `BACKLOG.md`
  retires the build and opens **B2** for the deploy, which is blocked on
  **Q-012** and, because `frontend/dist` is one bundle, on **Q-021** as well.
- **[#8](https://github.com/pumasi-ai/pumasi-sign/issues/8) — the app root has
  no product page in production.** Re-measured, not inherited from the previous
  evaluation:

  ```
  $ curl -s https://sign.pumasi.ai/ | grep -o '/assets/[^"]*\.js'
  /assets/index-j38Qwibz.js
  $ curl -s -o idx.js -w '%{http_code} %{size_download}\n' \
      https://sign.pumasi.ai/assets/index-j38Qwibz.js
  200 839941
  $ grep -oic 'landing' idx.js
  0
  ```

  Zero occurrences of `landing`, `LandingView` or `Apache-2.0`. **This
  evaluation went further and extracted the deployed route table**, which
  settles the question a string count only implies. Every route the shipped
  bundle registers: `/`, `/admin/users`, `/branding`, `/envelopes/:id`,
  `/login`, `/privacy`, `/send/draft/:draftId`, `/send/:templateId?`,
  `/signed-out`, `/sign/:submitterId`, `/sign/t/:accessUid`, `/templates`,
  `/templates/:id/build`, `/terms`, and the catch-all — with route names
  including `dashboard` and **not** `landing`. In production, `/` is the
  dashboard. (One case-insensitive `beta` match does occur in the bundle; it is
  inside the CSS counter-style name `tibetan` in a vendored library. The chip
  is not there.) The route is registered eagerly by name
  (`frontend/src/router/routes.ts:15`, moved there from `router/index.ts` at
  `d18d534`) with only its component lazy-loaded, so it would appear even if
  code-split. **`LandingView.vue` has never reached a user** — which is a
  different and stronger statement than "its correction is undeployed", and it
  is the correction this evaluation makes to §5. The remaining work is a
  deploy, not a build — and see §2.3. `BACKLOG.md` **B1**, which is why it is
  no longer in the numbered order.

### 2.3 · The public page made three claims the repository could not back; two are fixed in source, and **none of the three has ever been public**

**This section's framing was right and §5's row about it was wrong.** "Still
none of them is live" is true in the strongest possible sense, and this
evaluation's route-table measurement (§2.2) is what establishes it: the page
carrying all three claims has never been deployed at all. That is why this is a
gap and not an incident — and it is why the remedy is the *first* publication
of the page, correctly, rather than the repair of something users have seen.

1. **`BETA` — fixed in source at `a49f594`, and never public.** `frontend/src/stage.ts` now
   exports `STAGE = "alpha"` as the one constant, with `STAGE_LABEL` and
   `STAGE_BADGE` derived from it by expression; the template renders those
   rather than a hand-written rung. Frozen case **A-001** fails the build if
   this file's `**Current stage:**` line and that constant move apart — L-007
   closed by a gate rather than by a copy nobody checks.
2. **"Apache-2.0 (Open Source)" — not fixed, and correctly so.** The claim is
   still at `LandingView.vue:43`, `:80` and `:210`, and the repository still
   carries no `LICENSE`. **`pumasi/DECISIONS.md` Q-021** is open; its named
   default is to add the file, **and nobody has taken it** — `pumasi-web`
   marketing job `0035` raised exactly that to the steward at 12:58 on
   2026-08-31. Publishing a licence is an outward grant a third party may rely
   on, which is why CHARTER Part 0's reversibility rule does not release it.
   Frozen case **A-005** pins the three strings byte-identical to `10a523d` and
   retires with Q-021.
3. **Uncited competitor pricing — fixed in source at `a49f594`, and never public.** The table's
   figures now match [`MARKET.md`](MARKET.md) §1's cited rows, read from each
   vendor's own pricing page on 2026-08-31 and dated. Frozen cases **A-003**
   and **A-004** parse the figures and plan names out of `MARKET.md` at test
   time, so neither can fork from the file it checks — and A-003's haystack is
   restricted to `MARKET.md`'s **table rows**, because that file quotes the old
   false figures in prose in order to refute them (see §5's note on the shape).

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
says, and this must be closed before any `beta` promotion. `BACKLOG.md` **item 3**
(renumbered from item 5 in this evaluation's reorder).

**PR-1** binds *always*, at every stage, and is **still not met** — though the
gap has narrowed and the narrowing should be recorded rather than left to look
like inaction. A root `package.json` now exists (authored under `spec/0001` so
that `gate.sh` step 1 has something to run). It carries **no `version` field**,
deliberately and self-documentedly, to avoid taking a backlog item inside a
packet scoped to something else. So: `frontend/package.json` reads `0.0.0`
while `service/package.json` reads `0.1.0` (two hand-maintained copies, L-007),
no version is visible to a user anywhere in the SPA, there is no `/version`
endpoint, and `FeedbackDialog.vue::buildContext` (`:105`–`:122`) carries
thirteen fields and **not the version it concerns**. Every one of the five open
issues is therefore a defect report without a version. `BACKLOG.md` **item 4**
(renumbered from item 6). **Its cost rose at `d18d534`:** the root
`package.json` was edited there and its `version` field deliberately left
absent, pinned by frozen case **A-208** (`spec/0003/SPEC.md:211`) so that no
later packet takes this item in passing — so the packet that does take it must
retire or amend A-208 in the same commit.

### 2.5 · A merged fix reaches users at no defined time

Nothing in this project owns deployment: **Q-012** is open and explicitly
outside CHARTER Part 0's proceed-on-default rule, `CHARTER §2.1`'s flow ends at
a published release note, and no role file names deploying as a duty. **The
concrete cost has grown at every evaluation, and at this one it changed in
kind.** At first publication it was #8 alone. At the second it was #8 plus both
halves of the old item 1 (the honest stage chip and the cited pricing, merged
at `a49f594`) — all of them page content nobody had ever seen.

**At this one it is a live user-facing defect.** #7's fix is merged at
`d18d534`, a release note is published, `Q-027`'s 7-day window is running — and
a signed-out user on `sign.pumasi.ai` still gets `{"error":"Endpoint not
found"}` as a page. The undeployed set is four merged changes deep and one of
them is the repair of something breaking in front of a real person who reported
it. That is §5's genuine state (iii).

**And the two are now entangled, which is new and is not in Q-021's or Q-012's
text.** `service/wrangler.jsonc:8` serves `../frontend/dist` as one `ASSETS`
directory; `routes.ts:15` puts `LandingView` at `/`; `frontend/dist` is
`.gitignore`d and must be rebuilt for #7's fix to be in it. So **the only build
that carries the fix also publishes "Apache-2.0 (Open Source)"** on a
repository with no `LICENSE`. #7's repair cannot reach users without answering
Q-021, and it cannot reach them at all without answering Q-012. Raised as
`pumasi/DECISIONS.md` **Q-028** with a named default; recorded here, not routed
around.
Recorded as a known gap rather than argued about.

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
deliberately not in the same order.

1. **More than a PDF stamper for the gates to run** (`BACKLOG.md` **item 1**,
   Q-018, Q-025). Both earlier halves of this line are **done**: a CI job over
   `service/` at `ef851d6`, and the *merge* gate at `d18d534`. What is left is
   that what both of them run there is **two tests on one file**, and that the
   `e2e` suite — the only one that exercises routes — drives `backend/` rather
   than the worker. This is now the top of the backlog.
2. **#7's fix delivered to a user** — the build is done at `d18d534`; the
   deploy is not (**B2**, blocked on Q-012 and, per §2.5, Q-021). §2.2.
3. **Surface B live and honest** — #8 deployed, with §2.3's remaining claim made
   true or removed first (**B1**, blocked on Q-021 and Q-012).
4. **PR-2's screenshot made opt-in** (item 3).
5. **PR-1 met** — one version, user-visible, in every feedback report (item 4).
6. **Data survival evidenced** — a stated retention and backup posture for the
   Durable Object store and R2, citable from this file (item 15).
7. **A real end-to-end user completing a send-and-sign without an engineer**,
   which is STAGE_PLAYBOOK.md's Stage-2 exit gate and is the thing all of the
   above only make measurable.

---

## 4 · Known gaps, carried openly

- Two backends, one product; the deployed one is covered by two tests that
  exercise one file, and the `e2e` suite drives the other tree — so CI can be
  green on a live production 404, and at `d18d534` it is (§2.1, §2.2, Q-018,
  Q-025). **Changed at `d18d534`:** the merge gate now runs those two tests,
  where before it ran none of them. It is two, and they are on the PDF stamper.
- `main` is **not a protected branch**; CI reports and blocks nothing (§2.1).
- No `LICENSE`, while merged-but-undeployed public copy claims Apache-2.0
  (§2.3, Q-021).
- No version number (PR-1, §2.4).
- `README.md` still describes the product as "a minimal internal e-signature
  service for Pumasi employees … One FastAPI service, one Postgres database,
  one Railway volume", which is neither what the landing page sells nor what
  the live host runs. `CLAUDE.md` was corrected at `ef851d6`; `README.md` was
  not. Downstream of Q-018; listed so it is not rediscovered.
- Deployment has no owner (Q-012, §2.5), the undeployed set is now **four**
  merged changes deep, and as of `d18d534` it contains the repair of a **live**
  user-facing defect rather than only unpublished page copy.
- **The #7 repair and the unbacked licence claim can only ship together**, because
  `frontend/dist` is one bundle (§2.5). New this evaluation; raised as **Q-028**.
- **Closed since the first publication:** `roadmap/MARKET.md` did not exist and
  now does; competitor numbers in product code were uncited and now cite it.

---

## 5 · What this file now contradicts, and who fixes each

A stage set on evidence disagrees with files that were written before it
existed. Naming them is this file's job; editing them is not.

| Says | Where | State | Owner of the fix |
| :--- | :--- | :--- | :--- |
| *Sign in again* → `{"error":"Endpoint not found"}` | live on `sign.pumasi.ai`; fixed in `SignedOutView.vue` + `utils/http.ts` at `d18d534` | **(iii) Fixed in source, still wrong in production** — the one genuine example on this page. Measured this tick: `GET /api/auth/login?next=%2F` → `404`, and the shipped bundle still contains the helper `d18d534` deleted (§2.2) | **Nobody in the build queue.** The build is done. What is left is a **deploy** — **Q-012**, and per §2.5 **Q-021** too, because it ships in the same bundle as the licence claim. `BACKLOG.md` **B2**; raised as **Q-028**. |
| `BETA` chip and "in active Beta" | `frontend/src/views/LandingView.vue` | **Merged, never shipped** — *corrected in this evaluation; this row previously read "Fixed in source, live in production" and the second half was false.* `a49f594` replaced the chip with a constant derived from this file, and the page it sits on **has never been deployed**: the live bundle registers no `landing` route and `/` is the dashboard (§2.2). No user has ever seen this chip. | **Nobody in the build queue**, and the remedy is **the first deploy of the page**, not the deploy of a correction — which is why it cannot be taken before **Q-021**. `BACKLOG.md` **B1**. |
| "Apache-2.0 (Open Source)" | `LandingView.vue:43`, `:80`, `:210` | **Merged, never shipped**, unchanged, and correctly untouched — same page, same reason as the row above | **The steward**, via Q-021. `BACKLOG.md` **B1**; the named default is unclaimed. |
| Uncited competitor pricing (now cited) | `LandingView.vue` comparison table | **Merged, never shipped** — fixed at `a49f594` against `MARKET.md`; same page | **Nobody in the build queue.** B1's deploy. |
| `"status": "seed"` | `pumasi/catalog.json` | Read directly this tick; see below | **Nobody, today** — **Q-019**, open, and its default is a *role-file amendment* nobody has made. Not edited here. |

**The third state — and the fourth, which this evaluation had to add because
the third was being used for two different things.** A claim can be (i) wrong
in source and in production, (ii) right in both, (iii) **fixed in source and
still wrong in production**, or (iv) **merged and never shipped** — present on
`main`, absent from every deployment there has ever been, and therefore never
seen by anyone.

**The second evaluation filed the `BETA` chip under (iii). That was wrong, and
the correction is this evaluation's main change to this file.** The chip is in
(iv). The marketing manager that finished job `0038` measured this on
2026-08-31 at 18:49 UTC and correctly did not edit this register; this
evaluation re-measured it independently at 20:10–20:12 UTC and confirms it, by
extracting the deployed route table rather than counting a string (§2.2). Every
claim on `LandingView.vue` is in (iv), including the Apache-2.0 lines.

**Why the distinction is not pedantry.** It changes the remedy and it changes
who owns it. State (iii) reads as *deploy the correction* — an operational act
waiting on Q-012 alone. State (iv) is *publish the page for the first time*,
which cannot happen before **Q-021** answers what licence the page may claim.
Filing the chip under (iii) made B1 look like a scheduling problem when it is a
steward decision, and it invited a reader to believe users had met a false
`BETA` badge that in fact nobody has ever seen.

**State (iii) is not empty, though — it acquired its first real occupant at
`d18d534`, and job `0038` predicted its shape** (*"#7's inverse: live defect,
fix not merged"* — the merge has since happened, which is what completes it).
Issue #7 is live on `sign.pumasi.ai` today, its fix is on `main`, a release
note is published and Q-027's window is running. That is the row at the top of
the table, and it is the state that reads as done in a repository and is false
to a user. It is named here so that a later reader does not check
`SignedOutView.vue`, see `loginPageUrl`, and conclude the button works.

**`catalog.json`, read directly and recorded rather than edited** (Q-019 is
open; no seat may edit that file today, and this seat's `May Write` does not
include it). Both arrays were read by this evaluation at `pumasi` @ `a76aa3c`:

| Array | `pumasi-sign` | `pumasi-booking` | `pumasi-tunnel` |
| :--- | :--- | :--- | :--- |
| `products[]` | `"status": "seed"` | `"status": "seed"` | **absent** |
| `items[]` | `"status": "seed"` | `"maturity": "seed"` — **different key** | **absent** |

Three things follow, and the third is the one nobody had written down:

- Both arrays record `seed` for this product against **`alpha`** in this file.
  `seed` is not a rung on the role file's ladder at all, and nothing states how
  the two vocabularies map. The file's top-level `updated` still reads
  `2026-08-29`.
- `pumasi-tunnel` is absent from **both** arrays, though it serves live public
  surfaces. That is Q-019's opening fact and it is unchanged.
- **The two arrays disagree with each other on the field name**, and that is
  why two seats reported different things and neither was wrong.
  `items[]` uses `status` for `pumasi-sign` and `maturity` for
  `pumasi-booking` — adjacent entries, same concept, two keys. A reading of
  `products[]` correctly reports both products carrying `status: seed`; a
  reading of `items[]` correctly reports that `pumasi-booking` has no `status`
  field there. Recorded for whoever answers Q-019: the file is not merely
  stale, it is internally inconsistent, and any owner assigned to it inherits a
  schema question as well as a content one.

The commons product card (`pumasi-web/content/products/pumasi-sign.md`) sourced
its maturity from `catalog.json` and said so, because no stage file existed
(marketing job `0021`). **That is now done and this evaluation verified it by
reading the card**: its front matter reads `status: alpha`, its body cites
`roadmap/STAGE.md` by link as the source, it reproduces the Stage 1 row as
**IN PROGRESS — Surface A live, Surface B undeployed**, and it records that an
earlier version said `seed`. It also carries the `catalog.json` disagreement
above, as a stated gap rather than silently. Nothing is outstanding here; the
row is kept because the *`catalog.json`* half of it still is (**Q-019**).

**One thing the card must not be allowed to drift on, flagged forward rather
than edited here:** it says Surface B is undeployed, which is correct today. If
B1 or B2 ever deploys, that page and this file move together — and `pumasi-web`
is not this seat's to edit.

---

## Change log

| Date | Stage | Why |
| :--- | :--- | :--- |
| 2026-08-31 | `alpha` (first publication) | Live, in real use, feedback answered — but the green gate covers a tree no user reaches (2 tests on the deployed one, none in CI), two `priority: high` defects sit on the entry path, the root page is undeployed, and public copy claims a licence the repository does not carry. `beta` means strangers can rely on it and data survives; neither is evidenced. |
| 2026-08-31 | `alpha` (**unchanged** — second evaluation, at `ef851d6`) | One of the four reasons above moved and three did not. **Moved:** CI now runs the deployed tree, and its ability to fail was proven on real runs. **Did not move:** what that job runs is two tests on one file, and the *merge* gate runs none of them on a branch with no protection (§2.1); #7 is still open and is now **diagnosed** as a live `404` on the sign-in path, caused by the SPA calling a route only `backend/` has (§2.2); Surface B is still undeployed, re-measured on the same bundle filename as before (§2.2); and there is still no `LICENSE`. Determinism measured for the first time on this product — **40/40 and 40/40 on the two suites that could run, 0 runs on the two that could not** (§0 rider (b)). No promotion: Stage 1's exit gate needs both landing surfaces live and one is not, so **`STAGE_PLAYBOOK.md` Event 3 did not fire**. No demotion: nothing regressed, and rider (c) forbids demoting for evidence strength alone. |
| 2026-08-31 | `alpha` (**unchanged** — third evaluation, at `d18d534`) | Two of the reasons below moved, one correction was made to this file, and the rung did not change. **Moved:** the *merge* gate now runs the served tree — root `npm test` at `d18d534` reports `Test Files 6 (6)`, `Tests 85 (85)`, `# pass 2`, `# fail 0`, where before it reported 5/69 and zero service assertions — and #7's raw `404` is fixed in source. **Did not move:** what either gate runs on the served tree is still two tests on one file (now `BACKLOG.md` **item 1**, promoted to the top of the backlog for exactly that reason); `main` is still unprotected (404, re-checked); Surface B is still undeployed; there is still no `LICENSE`. **Corrected:** §5 filed the `BETA` chip as *fixed in source, live in production* — the second half was false. The page carrying it has never been deployed (route table extracted from the live bundle: no `landing` route, `/` is the dashboard), so it is **merged, never shipped**, and the remedy is the page's *first* deploy, which Q-021 gates. **§5's genuine state (iii) is #7**: live in production, fixed on `main`, undeployed — the first time this product has had one. Determinism re-measured for the suite that exists *today*, because `d18d534` changed its shape: **40 of 40**, identical counts every run (§0 rider (b)). No promotion: Stage 1's exit gate still needs both landing surfaces live and one is not, so **`STAGE_PLAYBOOK.md` Event 3 did not fire**. No demotion: nothing regressed. **New:** #7's fix and the unbacked Apache-2.0 claim can only ship in the same bundle — raised as **Q-028**. |
