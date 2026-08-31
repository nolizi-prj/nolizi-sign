# STAGE — Pumasi Sign

**Current stage:** `alpha`
**Set:** 2026-08-31, first publication of this file, at `5cb3bf8`.
**Re-evaluated:** 2026-08-31 (second evaluation), at `ef851d6`. **Stage
unchanged** — not promoted, not demoted. Evidence re-derived below.
**Stage 1 exit gate:** **NOT MET** — Surface B (the product's own root landing
page) is built and undeployed. Re-measured at `ef851d6`, §2.2.
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
source** — `a49f594` replaced it with a constant derived from this file — and
is **still live in production**, because nothing has deployed. §5 carries that
third state.

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
for every claim below:

| Evidence | Who re-ran it | When |
| :--- | :--- | :--- |
| CI run 33420378497 (`main` @ `ef851d6`, four jobs) | this evaluation, via `gh run view` | 2026-08-31 |
| The `service` job's ability to **fail** (runs 33419949879, 33419950651) | this evaluation, via `gh run view` | 2026-08-31 |
| `service/` suite, 40 consecutive runs | this evaluation, locally at `ef851d6` | 2026-08-31 |
| Root `npm test` (= `gate.sh` step 1), 40 consecutive runs | this evaluation, locally at `ef851d6` | 2026-08-31 |
| Live host: bundle, health, `/api/auth/login` | this evaluation, via `curl` | 2026-08-31 |
| `backend/` pytest (541 functions) | **nobody, here** — see rider (b) | — |

**And the merge gate itself is still unwitnessed on this repository.**
`pumasi/tools/gate.sh:25` runs `npm test` at this repository's root, and that
script is `cd frontend && npm run test:unit && npx vue-tsc -b --force` — the
string `service` occurs zero times in it. A coder can print `GATE: PASS` here
having run **zero** service tests, on the only tree that answers
`sign.pumasi.ai`. That is `BACKLOG.md` **item 2**, and it is Q-025's question
in this product's shape.

### Rider (b) — measure determinism, do not inherit a single green run

This product had **no** repeat-run figure on record. It now has two, and one
named absence. Raw counts, and the number of runs actually performed:

| Suite | Runs | Result | Per-run counts |
| :--- | ---: | :--- | :--- |
| Root `npm test` — **what `gate.sh` step 1 executes** | **40** | **40 pass, 0 fail** | every run: `Test Files 5 passed (5)`, `Tests 69 passed (69)` |
| `service/` `npm test` (built once at `ef851d6`) | **40** | **40 pass, 0 fail** | every run: `# pass 2`, `# fail 0` |
| `backend/` pytest — 541 test functions | **0** | **not run, not inherited** | — |
| `frontend/` Playwright e2e — 6 specs | **0** | **not run, not inherited** | — |

**On the two suites that could not be repeated, and why the number is 0 rather
than an estimate.** `backend/` pytest is Postgres-only by design: `pg_isready
-h localhost -p 5433` fails and a TCP connect to `127.0.0.1:5433` is refused on
this machine, and `docker` is not on `PATH`, so the container the README
prescribes cannot be started either. The Playwright job drives a Docker image
of `backend/` and fails for the same reason. **No rate is reported for either,
because none was run.** CI ran both green at `ef851d6` (run 33420378497) —
that is one observation, from CI, and it is recorded as one observation.

**The `service/` figure is stronger than a pass rate, and deliberately so.**
Each of the 40 runs was checked for its **reported assertion count**, not only
its exit status. `service`'s `test` script is `node --test dist/test/*.test.js`
against a `.gitignore`d `dist/`, and an unbuilt tree exits **0** having run
nothing (L-006; frozen case `spec/0002` A-103 pins exactly this). A pass rate
of 40/40 would have been satisfiable by 40 runs of nothing. All 40 reported
`# pass 2`.

**Context, not a claim about the fleet:** `pumasi-booking` measured 40 of 40
(job `0030`) and `pumasi-tunnel` found 3 failures in 40 (**Q-024**). Two
suites at 40/40 here is a good answer on the two suites that could run; it says
nothing about the 541 nobody re-ran.

### Rider (c) — CI-derived evidence and seat-derived evidence, ranked

No demotion is taken for lacking CI, and none is warranted: this product
**has** CI, and since `ef851d6` it covers the served tree. The rider's real
instruction is the other one — evidence re-derived by a seat that did not write
the code is **weaker than CI, and is written down as weaker**. Applied here:

- **Strongest — CI artefacts.** Runs 33420378497, 33419949879, 33419950651.
  Machine-run, third-party re-openable, and two of the three are *failures*
  deliberately produced to prove the new job can go red.
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
| **1 · Alpha** | Pure-core suite passes 100%; **both** public landing surfaces live | **IN PROGRESS** — Surface A live, Surface B undeployed (§2.2) |
| **2 · Beta** | Real end-to-end users complete workflows without engineer intervention | PENDING |
| **3 · Launched** | Production hardening, cross-model regression, 7-day veto window | PENDING |

---

## 1 · What is true, measured this tick

Measured 2026-08-31 against `main` @ `ef851d6` and against the live host, by
running the commands rather than by reading the claim. Provenance per §0.

**CI is green on `main`, and it now covers the tree users meet.** Run
[33420378497](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33420378497)
at `ef851d6`: `backend` ✓, `frontend` ✓, **`service` ✓**, `e2e` ✓. This closed
`BACKLOG.md`'s old item 2 and Q-018 parts (a)–(c) (coder job `0032`). **The
qualification that used to attach to this sentence is now smaller but not
gone** — see §2.1.

**The product is live and answers.** `GET https://sign.pumasi.ai/api/health`
→ `200 {"status":"ok","service":"pumasi-sign",…}`.

**Real people are using it and talking back.** Six issues arrived from the
in-app feedback widget between 2026-08-30 22:29 and 2026-08-31 14:47
([#4](https://github.com/pumasi-ai/pumasi-sign/issues/4)–[#9](https://github.com/pumasi-ai/pumasi-sign/issues/9));
**five remain open and all five carry a cited verdict** (#9 closed as another
product's defect — see §2.5). **No new issue has arrived since the last
evaluation**, so this evaluation's feedback intake is *quiet* and adds no
verdict. That is the `alpha` sentence exactly: it works for people who talk to
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

### 2.1 · The gate now covers the served tree; the *merge* gate does not, and what CI runs is two tests wide

This is still the one that matters most, and it has moved — in one half.

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

**What did not close, and is now the sharper half.** Two things:

**(i) The merge gate never runs it.** `pumasi/tools/gate.sh:25` is
`if npm test; then echo "   tests: PASS"`, and this repository's root
`package.json` `test` script is `cd frontend && npm run test:unit && npx
vue-tsc -b --force`. Zero occurrences of `service`. **And CI blocks nothing:**
`GET /repos/pumasi-ai/pumasi-sign/branches/main/protection` returns **404
"Branch not protected"**, measured this tick. So between a change and `main`
there is exactly one check, it is run by hand by the author of the change, and
it does not execute the deployed tree's suite. `BACKLOG.md` item 2; Q-025.

**(ii) What the new job runs is two tests, and they test one file.** Both
files in `service/src/test/` were **read in full** for this evaluation rather
than counted. They have identical import lists — `node:test`,
`node:assert/strict`, `pdf-lib`, and `stampAndCertifyPdf` from
`../core/stamping.js` — and nothing else. Three consequences:

- **`e2e-workflow.test.ts` is not an end-to-end test of anything.** It calls no
  route, starts no worker and touches no store; it is a second scenario against
  the same pure function. The file *name* over-states the coverage, and the
  first publication of this file's table row (`service/` | 2) let that pass.
- Both assert **shape, not content**: stamped bytes longer than the original,
  page count 2, two 64-hex-character hashes, and
  `notEqual(originalHash, completedHash)` — which passes for *any* mutation.
  Neither asserts that a signer's name, a date or a checkbox value reached the
  page.
- **Covered by nothing:** `durable.ts` (sessions, envelopes, signing, the whole
  API surface — including the `establishSession` domain-gate divergence Q-018
  flags), `worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`.

The two suites, recounted at `ef851d6`:

| Tree | Tests | Run by CI | Run by the merge gate |
| :--- | ---: | :--- | :--- |
| `backend/` | 541 test functions (545 collected in CI) | yes | no |
| `frontend/` unit | 69 in 5 files | yes | **yes** |
| `frontend/` e2e | 6 Playwright specs in 4 files | yes | no |
| **`service/` — the deployment** | **2, both on `core/stamping.ts`** | **yes, since `ef851d6`** | **no** |

This remains [L-006](https://github.com/pumasi-ai/governance/blob/main/lessons/L-006-tests-that-cannot-fail.md)
at suite scale and [L-009](https://github.com/pumasi-ai/governance/blob/main/lessons/L-009-two-paths-one-claim.md)
in a second product, and **Q-018 is open exactly as it was** — parts (a), (b)
and (c) of its *default* are taken; *which tree is the product* is untouched.
The claim this page may now make is narrow and is made narrowly: **CI exercises
the deployed tree's PDF stamper and nothing else about it.** No claim here
about production is read off the `backend` or `e2e` jobs, and none is.

### 2.2 · Two open `priority: high` defects on the entry path — one now diagnosed, one still undeployed

- **[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) — "sign in again"
  errors. The cause is no longer unknown.** The first publication of this file
  recorded it as *"no status code, unexplained"*, standing without a cause
  after #9 turned out to be another product's defect. Measured this tick
  against the live host:

  ```
  $ curl -s -i 'https://sign.pumasi.ai/api/auth/login?next=%2F'
  HTTP/2 404
  {"error":"Endpoint not found"}
  ```

  `SignedOutView.vue:26` renders *Sign in again* as `<a :href="signInUrl">`
  where `signInUrl = loginRedirectUrl("/")` = `/api/auth/login?next=%2F`
  (`utils/http.ts:30`) — a full-page navigation. **That route exists only in
  the tree nobody reaches**: `backend/app/routers/auth.py:82` is
  `@router.get("/login")` under prefix `/api/auth`, and `service/src/durable.ts`
  defines no `GET` under `/api/auth/login` at all — only
  `POST /api/auth/login/request` (`:775`) and `POST /api/auth/login/verify`
  (`:798`). So a signed-out user pressing the button is shown the worker's
  error JSON, raw. This is **L-009 in this product for the third time**, and it
  is the first one with a user on the other end of it. `BACKLOG.md` item 1.
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

  Zero occurrences of `landing`, `LandingView` or `Apache-2.0`. **The bundle
  filename is byte-for-byte the one the previous evaluation fetched**, which is
  itself the finding: nothing has deployed. And this is a *stronger* negative
  than a missing chunk would be — `router/index.ts:16` registers the route
  eagerly as `name: "landing"` and lazy-loads only its component, so the route
  name would appear in the main bundle even if the view were code-split, and
  `index.html` preloads no other chunk. The remaining work is a deploy, not a
  build — and see §2.3. `BACKLOG.md` **B1**, which is why it is no longer in
  the numbered order.

### 2.3 · The public page made three claims the repository could not back; two are fixed in source, none is fixed in production

Still none of them is live — the bundle above proves it — which is still the
only reason this is a gap and not an incident.

1. **`BETA` — fixed in source at `a49f594`.** `frontend/src/stage.ts` now
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
3. **Uncited competitor pricing — fixed in source at `a49f594`.** The table's
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
absence from main is not compliance; that entry has now been flagged by four
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
says, and this must be closed before any `beta` promotion. `BACKLOG.md` item 5.

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
issues is therefore a defect report without a version. `BACKLOG.md` item 6.

### 2.5 · A merged fix reaches users at no defined time

Nothing in this project owns deployment: **Q-012** is open and explicitly
outside CHARTER Part 0's proceed-on-default rule, `CHARTER §2.1`'s flow ends at
a published release note, and no role file names deploying as a duty. **The
concrete cost has grown since the first publication of this file.** Then it was
#8 alone. Now the undeployed set also includes both halves of the old item 1 —
the honest stage chip and the cited pricing, merged at `a49f594` — so the fix
for a claim this file itself objected to exists on `main` and users still meet
the false version. That is a third state, and §5 now has a row for it.
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

1. **A merge gate that runs the served tree** (`BACKLOG.md` item 2, Q-025) and
   **more than a PDF stamper for it to run** (item 4). The first half of this
   line — a CI job over `service/` — is **done** at `ef851d6`; what is left is
   that `GATE: PASS` still does not include it and that what it includes is two
   tests on one file.
2. **#7 explained and fixed**, on the tree that actually serves users (item 1).
   Now diagnosed; §2.2.
3. **Surface B live and honest** — #8 deployed, with §2.3's remaining claim made
   true or removed first (**B1**, blocked on Q-021 and Q-012).
4. **PR-1 met** — one version, user-visible, in every feedback report (item 6).
5. **PR-2's screenshot made opt-in** (item 5).
6. **Data survival evidenced** — a stated retention and backup posture for the
   Durable Object store and R2, citable from this file (item 17).
7. **A real end-to-end user completing a send-and-sign without an engineer**,
   which is STAGE_PLAYBOOK.md's Stage-2 exit gate and is the thing all of the
   above only make measurable.

---

## 4 · Known gaps, carried openly

- Two backends, one product; the deployed one is covered by two tests that
  exercise one file, and the merge gate runs neither (§2.1, Q-018, Q-025).
- `main` is **not a protected branch**; CI reports and blocks nothing (§2.1).
- No `LICENSE`, while merged-but-undeployed public copy claims Apache-2.0
  (§2.3, Q-021).
- No version number (PR-1, §2.4).
- `README.md` still describes the product as "a minimal internal e-signature
  service for Pumasi employees … One FastAPI service, one Postgres database,
  one Railway volume", which is neither what the landing page sells nor what
  the live host runs. `CLAUDE.md` was corrected at `ef851d6`; `README.md` was
  not. Downstream of Q-018; listed so it is not rediscovered.
- Deployment has no owner (Q-012, §2.5), and the undeployed set is now three
  merged changes deep, not one.
- **Closed since the first publication:** `roadmap/MARKET.md` did not exist and
  now does; competitor numbers in product code were uncited and now cite it.

---

## 5 · What this file now contradicts, and who fixes each

A stage set on evidence disagrees with files that were written before it
existed. Naming them is this file's job; editing them is not.

| Says | Where | State | Owner of the fix |
| :--- | :--- | :--- | :--- |
| `BETA` chip and "in active Beta" | `frontend/src/views/LandingView.vue` | **Fixed in source, live in production** — `a49f594` replaced it with a constant derived from this file; the deployment predates that commit (§2.2's bundle) | **Nobody in the build queue.** The code fix is merged. What is left is a **deploy**, which is Q-012 and is not this seat's to schedule. |
| "Apache-2.0 (Open Source)" | `LandingView.vue:43`, `:80`, `:210` | Merged, unchanged, and correctly untouched | **The steward**, via Q-021. `BACKLOG.md` **B1**; the named default is unclaimed. |
| `"status": "seed"` | `pumasi/catalog.json` | Read directly this tick; see below | **Nobody, today** — **Q-019**, open, and its default is a *role-file amendment* nobody has made. Not edited here. |

**The third state, which the first publication of this file did not have a row
for.** A claim can be (i) wrong in source and in production, (ii) right in
both, or (iii) **fixed in source and still wrong in production**. The `BETA`
chip is now in state (iii), and so is the competitor pricing. State (iii) is
the one that reads as done in a repository and is false to a user, and it is
the direct cost of Q-012 having no answer. It is named here so that a later
reader does not check `LandingView.vue`, see `STAGE_BADGE`, and conclude the
public page is honest.

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
(marketing job `0021`). One now does: **the marketing manager should re-source
that card from this file.** Still outstanding at this evaluation.

---

## Change log

| Date | Stage | Why |
| :--- | :--- | :--- |
| 2026-08-31 | `alpha` (first publication) | Live, in real use, feedback answered — but the green gate covers a tree no user reaches (2 tests on the deployed one, none in CI), two `priority: high` defects sit on the entry path, the root page is undeployed, and public copy claims a licence the repository does not carry. `beta` means strangers can rely on it and data survives; neither is evidenced. |
| 2026-08-31 | `alpha` (**unchanged** — second evaluation, at `ef851d6`) | One of the four reasons above moved and three did not. **Moved:** CI now runs the deployed tree, and its ability to fail was proven on real runs. **Did not move:** what that job runs is two tests on one file, and the *merge* gate runs none of them on a branch with no protection (§2.1); #7 is still open and is now **diagnosed** as a live `404` on the sign-in path, caused by the SPA calling a route only `backend/` has (§2.2); Surface B is still undeployed, re-measured on the same bundle filename as before (§2.2); and there is still no `LICENSE`. Determinism measured for the first time on this product — **40/40 and 40/40 on the two suites that could run, 0 runs on the two that could not** (§0 rider (b)). No promotion: Stage 1's exit gate needs both landing surfaces live and one is not, so **`STAGE_PLAYBOOK.md` Event 3 did not fire**. No demotion: nothing regressed, and rider (c) forbids demoting for evidence strength alone. |
