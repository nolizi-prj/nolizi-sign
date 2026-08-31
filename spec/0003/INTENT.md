# INTENT · 0003 — the way back in, and a gate that ran the tree it is read as covering

**Date:** 2026-08-31
**Source:** `roadmap/BACKLOG.md` items **1** and **2**, in one packet because
both entries close with *"take them in one packet."* Item 1 is issue
[#7](https://github.com/pumasi-ai/pumasi-sign/issues/7) (`accepted`,
`priority: high`); item 2 is coder job `0032`'s `SUGGESTED_NEXT_TASKS`
(`priority: high`), `pumasi/DECISIONS.md` **Q-025** rider (a), and
[`roadmap/STAGE.md`](../../roadmap/STAGE.md) §2.1.
**Repository:** `pumasi-sign`. Touches `frontend/src/`, the root
`package.json`, one new script under `.github/scripts/`, and `spec/`.
**Not touched:** `service/**`, `backend/**`, `.github/workflows/ci.yaml`,
`roadmap/**`.

## What is wrong — item 1

**A signed-out user who clicks the only button on the page is handed the
worker's error JSON.** Reproduced against `sign.pumasi.ai` and again against a
local `wrangler dev` of `service/` with a real browser, at `2bd3ba7`:

```
$ curl -s -i 'https://sign.pumasi.ai/api/auth/login?next=%2F'
HTTP/2 404
{"error":"Endpoint not found"}
```

The chain is three files long and none of it is a mystery:

- `frontend/src/views/SignedOutView.vue:26` renders *Sign in again* as
  `<v-btn :href="signInUrl">` — a full-document navigation, not a router push.
- `signInUrl` is `loginRedirectUrl("/")` (`:4`), and `loginRedirectUrl`
  (`frontend/src/utils/http.ts:30`) returns `/api/auth/login?next=<encoded>`.
- **`GET /api/auth/login` exists only in `backend/`** —
  `backend/app/routers/auth.py:82`, `@router.get("/login")` under prefix
  `/api/auth`. `service/src/durable.ts` defines no `GET` under
  `/api/auth/login` at all: only `POST /api/auth/login/request` (`:775`) and
  `POST /api/auth/login/verify` (`:798`).

`service/wrangler.jsonc` sets `run_worker_first: ["/api/*"]`, so the
navigation is *deliberately* routed past the SPA's assets layer to the worker,
which answers it as an unknown API endpoint. The user meets
`{"error":"Endpoint not found"}` as a document.

This is [L-009](https://github.com/pumasi-ai/governance/blob/main/lessons/L-009-two-paths-one-claim.md)
for the third time in this product: the frontend was written against
`backend/`, and `backend/` is not what serves users.

### The part that matters more than the bug

**All four CI jobs are green on this defect, and one of them is green
*because* of it.** Run
[33420378497](https://github.com/pumasi-ai/pumasi-sign/actions/runs/33420378497)
at `ef851d6` is `backend` ✓ `frontend` ✓ `service` ✓ `e2e` ✓ while the button
404s in production. `frontend/playwright.config.ts` boots `uvicorn`, or in CI
a Docker image built from the root `Dockerfile` — **`backend/` both times**,
the one tree in which that route exists. The six Playwright specs would keep
passing however long this stayed live, and none of them clicks this button
anyway (`grep -rn "Sign in again" frontend/e2e/` → no match).

So a green `e2e` job is not evidence about item 1, and this packet does not
offer one. The evidence it offers is a real browser driving a real
`wrangler dev` of `service/`, before and after, recorded in the
implementation commit.

## What is wrong — item 2

**`GATE: PASS` can be printed here having run zero tests on the tree that
answers `sign.pumasi.ai`.** Re-measured at `2bd3ba7`:

- `pumasi/tools/gate.sh:25` is `if npm test; then echo "   tests: PASS"`.
- This repository's root `package.json` `test` script is exactly
  `cd frontend && npm run test:unit && npx vue-tsc -b --force`. The string
  `service` occurs **zero** times in it, and zero times in `gate.sh`.
- Baseline run at `2bd3ba7`: `Test Files 5 passed (5) · Tests 69 passed (69)`
  — every one of them a frontend unit test. **Service assertions executed: 0.**
- `GET /repos/pumasi-ai/pumasi-sign/branches/main/protection` → **404 "Branch
  not protected"**. The `service` CI job reports; it blocks nothing.

`ef851d6` gave CI a `service` job, which is why this entry is now about what a
string in a release note *evidences* rather than about whether production code
is exercised at all. But between a change and `main` there is exactly one
check — run by hand, by the author — and it does not run the deployed tree's
suite. That is **Q-025**'s question in its sharpest form in the fleet.

### The trap inside this half, already named by the tree

`service/package.json`'s `test` is `node --test dist/test/*.test.js`: the
**compiled** tree, and `service/dist/` is `.gitignore`d. `node --test` exits
**0** on an unmatched glob. A root `test` script that ran `npm test` in
`service/` without building first would print `GATE: PASS` off zero
assertions — the same defect it exists to close, one level up. That trap
already has a guard (`.github/scripts/assert-service-suite-ran.sh`) and a
frozen case (**A-103**, **A-104**) from `spec/0002`. This change **reuses that
guard rather than writing a second one**; one guard in one place is the
difference between a rule and two restatements of it (L-007).

## What this change does

1. **The *Sign in again* button points at the SPA's own `/login` page**, via
   `loginPageUrl` — the helper defined one function below the broken one in
   the same file, and already what the `401` interceptor uses twelve lines
   further down. `loginRedirectUrl` is deleted; it has no other caller.
2. **The root `test` script runs both suites** — the frontend one it already
   ran, unshrunk, plus `service/`'s, installed and built first and then proved
   to have run by the existing guard.

## What this change deliberately does not do

- **It does not deploy.** **Q-012** is open and is explicitly outside CHARTER
  Part 0's proceed-on-default rule. **Q-018** adds that shipping this product
  means `wrangler deploy` from `service/`, not the Railway push — a run that
  followed `CLAUDE.md`'s Railway section would deploy a tree no user reaches.
  Neither is done here. **The fix is merged and undeployed, and the release
  note says so in those words.**
- **It does not answer Q-018.** Repair 1 was chosen partly *because* it is
  neutral to that question — see `SPEC.md` §S1.
- **It does not touch `roadmap/**`.** Retiring items 1 and 2 is a report to
  the product manager, not an edit this seat makes.
- **It does not take `BACKLOG.md` item 3** (`#6`, the inert `gap-*` classes).
  That entry says it "ships free alongside item 1" *if* item 1 opens
  `frontend/src/views/LoginView.vue`. The chosen repair does not open that
  file — it opens `SignedOutView.vue` and `utils/http.ts` — so item 3 is left
  for its own packet rather than the spec being widened to reach it.
- **It does not add a `version` field to the root `package.json`**
  (**PR-1**, `BACKLOG.md` item 6). Its absence is asserted as a frozen case so
  that "while I was in this file" cannot quietly take the product manager's
  next item.
- **It does not restructure `.github/workflows/ci.yaml`.** Making CI and the
  gate call one shared runner would be the tidier shape, and it is not taken:
  `spec/0002`'s frozen cases **A-101**, **A-102** and **A-105** pin that
  workflow's step shape, and this seat may not edit frozen cases. The bounded
  duplication that leaves is stated in `SPEC.md` §S4 rather than left for a
  reviewer to find.
