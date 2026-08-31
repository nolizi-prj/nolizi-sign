# STAGE — Pumasi Sign

**Current stage:** `alpha`
**Set:** 2026-08-31, first publication of this file, at `5cb3bf8`.
**Stage 1 exit gate:** **NOT MET** — Surface B (the product's own root landing
page) is built and undeployed. Evidence below.
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

**The stage is set by evidence, not by aspiration or by a chip.** A public page
in this repository says `BETA`. This file says `alpha`, and section 5 names
that disagreement and who resolves it.

---

## Maturity gates

| Stage | Criteria (STAGE_PLAYBOOK.md) | Status |
| :--- | :--- | :--- |
| **0 · Candidate** | Steward selection | **COMPLETE** — built and deployed |
| **1 · Alpha** | Pure-core suite passes 100%; **both** public landing surfaces live | **IN PROGRESS** — Surface A live, Surface B undeployed |
| **2 · Beta** | Real end-to-end users complete workflows without engineer intervention | PENDING |
| **3 · Launched** | Production hardening, cross-model regression, 7-day veto window | PENDING |

---

## 1 · What is true, measured this tick

Measured 2026-08-31 against `main` @ `5cb3bf8` and against the live host, by
running the commands rather than by reading the claim.

**CI is green on `main`.** Run
[33410370102](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33410370102):
`backend` ✓, `frontend` ✓, `e2e` ✓. This closed the red gate that was
`BACKLOG.md` item 1 (coder job `0018`, ops `DIGEST.md` 2026-08-31).

**The product is live and answers.** `GET https://sign.pumasi.ai/api/health`
→ `200 {"status":"ok","service":"pumasi-sign","time":"2026-08-31T15:57:01Z"}`.

**Real people are using it and talking back.** Six issues arrived from the
in-app feedback widget between 2026-08-30 22:29 and 2026-08-31 14:47
([#4](https://github.com/pumasi-ai/pumasi-sign/issues/4)–[#9](https://github.com/pumasi-ai/pumasi-sign/issues/9)),
all six now carry a cited verdict. That is the `alpha` sentence exactly: it
works for people who talk to the builders, and it breaks in front of them.

**Surface A is live.** `https://pumasi.ai/products/pumasi-sign/` → 200
(`pumasi-web` `content/products/pumasi-sign.md`).

---

## 2 · Why not `beta`

`beta` in the role file's own table means **strangers can rely on it, known
gaps are listed here, and data survives**. Five verified facts say not yet.
Each is a `BACKLOG.md` entry; the order below is not the backlog's — the
backlog orders by what to build next, this orders by what is furthest from
`beta`.

### 2.1 · The green gate covers a tree no user reaches

This is the one that matters most, and it is why "CI is green" appears in
section 1 with a qualification rather than as a promotion argument.

`sign.pumasi.ai` is served by the Cloudflare Worker in `service/`, not by the
FastAPI app in `backend/`. Re-verified here, not inherited: `POST
https://sign.pumasi.ai/api/auth/dev-login` — a real
`backend/app/routers/auth.py` route — returns `404 {"error":"Endpoint not
found"}`, the worker's error body; FastAPI answers `{"detail": …}`. `GET
/api/auth/me` returns `401 {"error":"Not signed in"}`, the worker's shape.

The two suites, counted:

| Tree | Tests | Run by CI |
| :--- | ---: | :--- |
| `backend/` | 541 test functions (545 collected in CI) | yes |
| `frontend/` e2e | 6 Playwright specs in 4 files | yes |
| **`service/` — the deployment** | **2** (`e2e-workflow.test.ts`, `stamping.test.ts`) | **no** |

`.github/workflows/ci.yaml` contains no occurrence of the string `service`.
The `service/` suite was built and run here on 2026-08-31 — `npm run build &&
npm test` in `service/`, exit 0, **2 tests, 2 pass, 0 fail** — so the code is
not untested; it is *ungated*, and it is two tests wide.

That is [L-006](https://github.com/pumasi-ai/governance/blob/main/lessons/L-006-tests-that-cannot-fail.md)
at suite scale and [L-009](https://github.com/pumasi-ai/governance/blob/main/lessons/L-009-two-paths-one-claim.md)
in a second product, and it is open as **`pumasi/DECISIONS.md` Q-018**
(*which implementation is Pumasi Sign?*). Until Q-018's part (b) exists — a CI
job over `service/` — **no claim on this page about production may be read off
the `backend` or `e2e` job**, and none is.

### 2.2 · Two open `priority: high` defects, both on the entry path

- **[#8](https://github.com/pumasi-ai/pumasi-sign/issues/8) — the app root has
  no product page in production.** `LandingView.vue` and its public `/` route
  were merged in `10a523d`; the deployment does not have them. Verified this
  tick: `https://sign.pumasi.ai/assets/index-j38Qwibz.js` fetched at HTTP 200,
  839 941 bytes, **zero occurrences of `landing`**. The remaining work is a
  deploy, not a build — and see 2.3 before that deploy happens.
- **[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) — "sign in again"
  errors.** Reported 2026-08-31 01:14, no status code, unexplained. It was
  provisionally linked to #9; #9 turned out not to be this product's defect at
  all (see 2.5), which removes the explanation and leaves the report standing.
  A user who is signed out and cannot get back in is the plainest possible
  counterexample to "strangers can rely on it".

### 2.3 · The public page makes three claims the repository does not back

None of these are live yet — the bundle above proves it — which is the only
reason this is a gap and not an incident. The deploy that closes #8 is the
moment they become public claims.

1. **`BETA`.** `frontend/src/views/LandingView.vue:34` ships a `BETA` chip and
   the banner text "Pumasi Sign is in active Beta". This file says `alpha`.
   STAGE_PLAYBOOK.md's Stage-1 Surface B deliverable asks for a prominent
   `[ALPHA - ACTIVE DEVELOPMENT]` badge, so the chip contradicts the playbook
   as well as this file.
2. **"Apache-2.0 (Open Source)".** The banner and the comparison table's last
   row both claim it. **There is no `LICENSE` file in this repository**, and
   `gh repo view --json licenseInfo` returns `null` — a public repository with
   no licence grants no rights at all. Sibling products carry the file
   (`pumasi-web/LICENSE`, `pumasi-tunnel/LICENSE`, both Apache-2.0), so this
   reads as an omission rather than a decision; it is raised as
   **`pumasi/DECISIONS.md` Q-021** with "add the file" as the named default.
3. **Uncited competitor pricing.** The comparison table asserts DocuSign at
   "$25 – $65 / user / mo" and a "100 / yr hard cap", and SignWell at
   "$10 – $30 / user / mo", with no source. This project has already published
   and then removed one uncited competitor claim (`pumasi-booking` `0d1674d`);
   the product-manager role forbids stating one "ever". Competitor numbers
   belong in `roadmap/MARKET.md` with citations, and the page may then cite
   that file. `MARKET.md` does not exist yet for this product.

### 2.4 · "Data survives" is not established, and one open entry contemplates dropping it

`beta` promises data survival. Real accounts, sessions and signed documents
live in the worker's Durable Object SQLite store and its R2 bucket. There is no
backup, restore or retention evidence in this repository to cite, and Q-018's
named alternative — FastAPI on Railway is the product — states in terms that
under that branch the worker's data "must be migrated or knowingly dropped".
A stage label cannot promise survival while a live decision entry lists
dropping it as an option the steward may still take.

Separately, `beta` is the rung at which **PR-2** binds (`PRODUCT-RULES.md`
v1.0, read this packet from `pumasi` branch `worktree-product-rules`
`0115758` — it is not on `pumasi` main, which is Q-017, and absence from main
is not compliance). PR-2 is satisfied in substance here: three kinds
(bug / enhancement / question), landing as public GitHub issues labelled
`feedback`, URL parameters matching `token|state|code|session|secret|key|auth|password`
redacted before they leave (`service/src/feedback.ts:32`), errors as message +
location, optional contact, and the composed report shown before send. **One
divergence**, and it is the privacy-shaped one: the screenshot is
**auto-captured and pre-attached** (`FeedbackDialog.vue:188`) rather than
attached by the user, against PR-2's "a screenshot travels only when the user
attaches one". In an e-signature product the page being captured is somebody's
contract, which is CHARTER §5.2's *never the user's own material*. The user can
see it and remove it, so it is opt-out and informed — but opt-out is not what
the rule says, and this must be closed before any `beta` promotion.

**PR-1** binds *always*, at every stage, and is **not** met today: there is no
root `package.json`, `frontend/package.json` reads `0.0.0` while
`service/package.json` reads `0.1.0` (two hand-maintained copies, L-007), no
version is visible to a user anywhere in the SPA, there is no `/version`
endpoint, and the feedback report's context block
(`FeedbackDialog.vue::buildContext`) carries page, browser, platform, viewport
and timezone but **not the version it concerns**. Every one of the six issues
above is therefore a defect report without a version.

### 2.5 · A merged fix reaches users at no defined time

Nothing in this project owns deployment: **Q-012** is open, `CHARTER §2.1`'s
flow ends at a published release note, and no role file names deploying as a
duty. The concrete cost here is #8 — the page exists on `main` and users meet a
five-commit-old bundle. This is recorded as a known gap rather than argued
about: whichever way Q-012 lands, a stage that claims strangers can rely on the
product needs a defined path from merge to user.

### On #9, which is *not* a reason

[#9](https://github.com/pumasi-ai/pumasi-sign/issues/9) ("login and signup
failure", `priority: high` when this evaluation opened) was the strongest
single argument against any promotion. It does not survive contact with the
evidence: coder job `0018` established against the live host that the
worker **cannot emit a `403` at all** (every status it returns was grepped),
that its `establishSession` (`service/src/durable.ts:655`) has no domain gate,
and that the reporter's exact wording occurs once in the fleet — in
`pumasi-booking`. #9 is closed here as not this product's defect. It is
recorded in this section rather than dropped, because a stage file that quietly
loses its own strongest counter-argument is not evidence.

---

## 3 · What `beta` requires

In the order that reduces the distance fastest. Each maps to a `BACKLOG.md`
entry; this list is the *gate*, the backlog is the *schedule*.

1. **A CI gate over `service/`** (Q-018 part (b)), and `CLAUDE.md` naming the
   worker as production (part (a)). Nothing else on this list can be believed
   before this one exists.
2. **Surface B live and honest** — #8 deployed, with 2.3's three claims made
   true or removed first.
3. **#7 explained**, on the tree that actually serves users.
4. **PR-1 met** — one version, user-visible, in every feedback report.
5. **PR-2's screenshot made opt-in.**
6. **Data survival evidenced** — a stated retention and backup posture for the
   Durable Object store and R2, citable from this file.
7. **A real end-to-end user completing a send-and-sign without an engineer**,
   which is STAGE_PLAYBOOK.md's Stage-2 exit gate and is the thing all of the
   above only make measurable.

---

## 4 · Known gaps, carried openly

- Two backends, one product; the deployed one has two tests and no gate (2.1,
  Q-018).
- No `LICENSE`, while public copy claims Apache-2.0 (2.3, Q-021).
- No `roadmap/MARKET.md`; competitor numbers are currently asserted in product
  code without citation (2.3).
- No version number (PR-1, 2.4).
- `README.md` still describes the product as "a minimal internal e-signature
  service for Pumasi employees … One FastAPI service, one Postgres database,
  one Railway volume", which is neither what the landing page sells nor what
  the live host runs. Downstream of Q-018; listed so it is not rediscovered.
- Deployment has no owner (Q-012, 2.5).

---

## 5 · What this file now contradicts, and who fixes each

A stage set on evidence disagrees with two files that were written before it
existed. Naming them is this file's job; editing them is not.

| Says | Where | Owner of the fix |
| :--- | :--- | :--- |
| `BETA` chip and "in active Beta" | `frontend/src/views/LandingView.vue:34` | **The coder**, as `BACKLOG.md` item 1 — it is product code, which this role may not edit. The marketing manager owns the same claim wherever it appears in `web/` or `pumasi-web`. |
| `"status": "seed"` | `pumasi/catalog.json`, `products[]` and `items[]` | **Nobody, today** — that file has no owner in any role file, which is **Q-019**, raised 2026-08-31. Under Q-019's named default this row would become this role's, updated in the same commit as this file. It was not edited here. Note the two files also use two vocabularies: `seed` is not a rung on the role file's ladder, and nothing states how they map. |

The commons product card (`pumasi-web/content/products/pumasi-sign.md`) sourced
its maturity from `catalog.json` and said so, because no stage file existed
(marketing job `0021`). One now does: **the marketing manager should re-source
that card from this file.**

---

## Change log

| Date | Stage | Why |
| :--- | :--- | :--- |
| 2026-08-31 | `alpha` (first publication) | Live, in real use, feedback answered — but the green gate covers a tree no user reaches (2 tests on the deployed one, none in CI), two `priority: high` defects sit on the entry path, the root page is undeployed, and public copy claims a licence the repository does not carry. `beta` means strangers can rely on it and data survives; neither is evidenced. |
