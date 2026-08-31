# INTENT · 0002 — the gate covers the tree users actually meet

**Date:** 2026-08-31
**Source:** `roadmap/BACKLOG.md` item 2 = `pumasi/DECISIONS.md` **Q-018**
parts **(a)** and **(b)**, and only those.
**Repository:** `pumasi-sign`. Touches `.github/`, `CLAUDE.md`, `spec/` and
one new test file under `frontend/src/`. No product code.

## What is wrong

**This repository ships two complete backends for one product, and CI tests
only the one nobody reaches.** Measured against `a49f594`, this tick:

- `.github/workflows/ci.yaml` defines **three** jobs — `backend` (line 10),
  `frontend` (line 60), `e2e` (line 89). **None of them builds, lints, type-
  checks or runs anything under `service/`.**
- `backend/` carries **541** `def test_` functions and the `e2e` job drives
  Playwright against a Docker image built from that same FastAPI tree.
- `service/` — the Cloudflare Worker whose `wrangler.jsonc` claims
  `sign.pumasi.ai` as a `custom_domain`, and which Q-018 verified live is
  what answers that host — carries **two** test files
  (`src/test/stamping.test.ts`, `src/test/e2e-workflow.test.ts`, one `test()`
  each) and **no CI job at all**.
- `CLAUDE.md` — the file every agent in this repository reads first — opens
  by calling the product a "FastAPI backend … hosted on Railway" and closes
  with a Deployment section whose commands are all `railway up`. It never
  mentions `service/`, `wrangler`, Cloudflare, or `sign.pumasi.ai`.

So a run that believed `CLAUDE.md` would deploy a tree no user reaches and
report it as shipped — Q-018 says exactly that — and every "541 tests pass"
in this repository's history has been read as covering a deployment it does
not touch. That is
[L-006](https://github.com/pumasi-ai/governance/blob/main/lessons/L-006-tests-that-cannot-fail.md)
at suite scale: a green gate that cannot fail for the thing it is read as
covering.

## The trap inside the fix, measured before it was designed around

`service/package.json`'s own `test` script is
`node --test dist/test/*.test.js` — it runs the **compiled** tree, and
`service/dist/` is `.gitignore`d, so a fresh CI checkout has none. Measured
on a clean `git archive` of `a49f594` with `dist/` absent:

```
> node --test dist/test/*.test.js
1..0
# tests 0
# pass 0
# fail 0
      exit 0
```

**A `service` job that runs `npm test` without building first is a green job
that executes zero assertions** — the same defect one level up from the one
being closed. Naming that is most of this change's value, so the job is built
to be unable to do it, and the guard that makes it unable is itself a frozen
acceptance case (A-104) rather than a comment.

## What this change does

1. **`CLAUDE.md` names the deployed tree.** It describes both trees, says
   which one serves `sign.pumasi.ai` and by which command, marks the Railway/
   FastAPI stack as the second implementation that is not in production, and
   points at Q-018 as the open question of which one *is* the product. It also
   stops documenting `npx vue-tsc --noEmit` as the frontend type-check —
   re-measured this tick, that command exits 0 on a tree with a deliberate
   type error (see below).
2. **`ci.yaml` gains a `service` job** that installs, builds and runs
   `service/src/test/`, and then asserts the suite actually ran. It fails when
   `service/` breaks, and it fails when it is handed an unbuilt tree.
3. **`ci.yaml`'s frontend Type-check step stops being decorative.**
   Re-measured against `a49f594` with `const x: number = "s"` appended to
   `frontend/src/stage.ts`: `npx vue-tsc --noEmit` → **exit 0**;
   `npx vue-tsc -b` → **exit 2**; `npx vue-tsc -b --force` → **exit 2**.
   `frontend/tsconfig.json` is a solution file (empty `files`, two
   `references`), so without `-b` there is no program to check. This agrees
   with job `0026`'s measurement. CI was not blind — the Build step beside it
   runs `vue-tsc -b && vite build` and does catch it — so this is one
   decorative step next to a real one, and `0026` fixed it only in the root
   `package.json` gate adapter, leaving `ci.yaml` and `CLAUDE.md` named for
   this item.

## What this change deliberately does not do

- **It does not decide which tree is Pumasi Sign.** Retiring `backend/`,
  re-pointing the domain, or migrating data are the other half of Q-018 and
  are the steward's. Nothing is deleted: not a test, not a job, not a
  directory. Q-018's default part (c) — *no claim about production is read off
  the `backend`/`e2e` jobs* — is honoured by saying so in `CLAUDE.md`, not by
  removing those jobs.
- **It does not write `service/` features.** `service/` has two tests and both
  exercise `core/stamping.ts` only. Its auth, its Durable Object store, its R2
  layer and its mail path are covered by nothing. That is a real and serious
  gap, and it is a finding for the product manager — not a licence for this
  seat to invent tests to give a new job something to run.
- **It does not touch `LandingView.vue`.** The three Apache-2.0 strings are
  Q-021 and the steward's; `spec/0001`'s frozen case **A-005** already proves
  they are unchanged and keeps proving it here.
- **It does not deploy.** Q-012 is open and explicitly outside CHARTER Part
  0's proceed-on-default rule. No `wrangler deploy`.
- **It does not edit `roadmap/`.** `BACKLOG.md` is the product manager's and
  still ranks item 1 as pending in full; it does not know that halves (a) and
  (c) landed at `a49f594`. Job `0026` deliberately left it alone and so does
  this one. It is reported, not corrected.

## What is unsure, with the answer taken on silence

1. **Does "make the gate cover the tree users actually meet" include
   `pumasi/tools/gate.sh`?** That gate's step 1 runs `npm test` at this
   repository's root, and the root `package.json` runs the frontend suite
   only — so after this change CI covers `service/` and the *merge gate* still
   does not. **Assumed on silence: no.** `BACKLOG.md` item 2 and Q-018 (b)
   both say *CI gains a job*, in those words, and the root `package.json` was
   written one commit ago by `0026` under a spec that scoped it. Widening it
   is reported as a finding instead.
2. **Should the `service` job also lint or type-check separately?** `service/`
   has no linter configured, and its build *is* `tsc -p tsconfig.json`, so the
   build step is the type-check. **Assumed on silence: no separate step.**

## Who this can cost

Nobody, today. This change adds a CI job and edits documentation; it alters no
service path, no auth, no data, and no user-visible surface. The cost it
*imposes* is on future work: a push that breaks `service/` will now go red
where it used to go green. That is the entire point.

---

**Published under CHARTER Part 2.1.** `roadmap/STAGE.md` records this product
at `alpha`, so CHARTER **Part 0** applies: open windows do not hold work and
agents proceed immediately, with the window recorded rather than waited out.
The steward's veto reverts rather than prevents. Nothing here is irreversible:
no credential, no mail, no publication of a person's data, no licence grant.
