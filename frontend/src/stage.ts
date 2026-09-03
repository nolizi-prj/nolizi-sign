/**
 * The product's published stage, and every user-facing form of it.
 *
 * ONE PLACE. The constant below is the only stage word written anywhere in
 * this frontend; the badge and the prose label are derived from it by
 * expression. Do not hand-write a rung into a template, a comment or a chip
 * — that is exactly how the landing page came to announce a stage the
 * product did not have (roadmap/BACKLOG.md item 1a, roadmap/STAGE.md §5),
 * and it is L-007's whole subject.
 *
 * THE REGISTER IS `roadmap/STAGE.md`, not this file. That file records which
 * rung the product is on and on what evidence; this constant must agree with
 * its `**Current stage:**` line, and acceptance case A-001
 * (`landing-claims.spec.ts`) fails the build when the two move apart.
 *
 * Why a test and not a build-time read: `Dockerfile`'s SPA stage copies only
 * `frontend/`, so `../roadmap/` does not exist where the bundle is built, and
 * a `vite.config.ts` read of it would break the e2e job's `docker build`. The
 * agreement is enforced by a gate rather than by a copy nobody checks — see
 * `spec/0001/SPEC.md` §S1.
 *
 * To move the stage: change `roadmap/STAGE.md` first, with its evidence, then
 * this line. The order matters — the register leads, the page follows.
 */
export const STAGE = "alpha";

/** Title-cased for prose: "Nolizi Sign is in active {{ STAGE_LABEL }}". */
export const STAGE_LABEL = STAGE.charAt(0).toUpperCase() + STAGE.slice(1);

/**
 * The prominent stage badge `pumasi-ops/STAGE_PLAYBOOK.md` asks every
 * product's own landing page to carry. Derived, so it follows the register
 * to the next rung on its own.
 */
export const STAGE_BADGE = `${STAGE.toUpperCase()} — ACTIVE DEVELOPMENT`;
