# Acceptance cases · spec/0002

The cases are not copied here. They live where their runner finds them, and
this file points at them — a second copy would fork from the first (L-007).

| # | Case | File | Runner | CI job |
| :-- | :--- | :--- | :--- | :--- |
| A-100 | guard on the reader the cases below use | [`frontend/src/ci-covers-service.spec.ts`](../../../frontend/src/ci-covers-service.spec.ts) | `vitest` | `frontend` |
| A-101 – A-102, A-105 – A-109 | `.github/workflows/ci.yaml` and `CLAUDE.md`, read as text | same file | `vitest` (`npm run test:unit` in `frontend/`) | `frontend` |
| A-103 | `service/package.json`'s own `test` script, executed in an empty directory | same file | `vitest` | `frontend` |
| A-104 | [`.github/scripts/assert-service-suite-ran.sh`](../../../.github/scripts/assert-service-suite-ran.sh), executed against fixtures | same file | `vitest` | `frontend` |

**They run in the `frontend` job on purpose.** A case that proves the
`service` job exists cannot live inside the `service` job: delete the job and
the case would stop running rather than go red. Every case here runs in a job
that was already green before this change.

They also run in the local merge gate, since
`pumasi/tools/gate.sh` step 1 is `npm test` at the repository root and the
root `package.json` runs `frontend`'s unit suite.

**What they do not cover.** They assert what `ci.yaml` *says*. What GitHub
Actions *does* with it is proven by pushing the mutations to scratch branches
and reading the runs; those URLs are in the implementation commit and in
`SPEC.md`'s amendment/evidence notes.

**Frozen** at the spec review for [`../SPEC.md`](../SPEC.md), before
implementation. Amending one takes an amended spec and a fresh cross-family
spec review (CHARTER Part 3 req 2) — not an edit here.
