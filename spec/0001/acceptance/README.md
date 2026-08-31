# Acceptance cases · spec/0001

The cases are not copied here. They live where their runners find them, and
this file points at them — a second copy would fork from the first (L-007).

| # | Case | File | Runner | CI job |
| :-- | :--- | :--- | :--- | :--- |
| A-001 – A-005 | source-level: the stage constant against `roadmap/STAGE.md`; one stage word in one place; every `$` figure against `roadmap/MARKET.md`; plan names and meter words; the Apache-2.0 scope guard | [`frontend/src/landing-claims.spec.ts`](../../../frontend/src/landing-claims.spec.ts) | `vitest` (`npm run test:unit` in `frontend/`) | `frontend` |
| A-006 | rendered: `/` as a signed-out visitor meets it | [`frontend/e2e/landing-page.spec.ts`](../../../frontend/e2e/landing-page.spec.ts) | Playwright (`npx playwright test`) | `e2e` |

Both read `roadmap/STAGE.md` and `roadmap/MARKET.md` at test time. Neither
copies a figure or a stage word out of them.

**Frozen** at the spec review for [`../SPEC.md`](../SPEC.md), before
implementation. Amending one takes an amended spec and a fresh cross-family
spec review (CHARTER Part 3 req 2) — not an edit here.

**A-005 retires with `pumasi/DECISIONS.md` Q-021.** See `SPEC.md` §S3 and the
comment at the case.
