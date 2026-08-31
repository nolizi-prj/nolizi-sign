# SPEC · 0001 — landing page: stage from the register, prices from MARKET.md

**Intent:** [`INTENT.md`](INTENT.md) · **Backlog:** item 1 halves (a) and (c)
**Frozen:** at spec review, before implementation.

The rules this change is measured against are not restated here (L-007):
`pumasi/governance/CHARTER.md`, `pumasi/PRODUCT-RULES.md` (v1.0, on branch
`worktree-product-rules` `0115758` — Q-017), `pumasi/lessons/L-006` and
`L-007`, `pumasi-ops/STAGE_PLAYBOOK.md`. The facts it is measured against are
[`roadmap/STAGE.md`](../../roadmap/STAGE.md) and
[`roadmap/MARKET.md`](../../roadmap/MARKET.md), read at test time rather than
copied.

---

## S1 · The stage is written in one place, and that place agrees with the register

**S1a.** A module `frontend/src/stage.ts` holds the product's stage as a
single constant, and derives every user-facing form of it (badge text, prose
label) by expression from that constant. No second stage word is written
anywhere in the frontend.

**S1b.** `LandingView.vue` writes **no** stage word. Its chip and its banner
sentence both interpolate the derived values from S1a.

**S1c.** The constant equals what `roadmap/STAGE.md` records on its
`**Current stage:**` line.

**S1d.** The badge follows `STAGE_PLAYBOOK.md`'s Stage-1 Surface B
deliverable in substance — the stage, upper-cased, plus `ACTIVE DEVELOPMENT`
— and follows it automatically at the next rung, because it is derived.

### Why the register is not read at build time

Reading `roadmap/STAGE.md` from `vite.config.ts` would be the strictly
single-source answer and it **cannot be done here**: `Dockerfile:6` copies
only `frontend/` into the SPA build stage, so `../roadmap/` does not exist
where the bundle is built, and `.dockerignore` excludes `docs`. A build-time
read would break the `e2e` CI job's `docker build`.

The agreement between the constant and the register is therefore enforced by
a **test that reads both** (A-001) rather than by a copy nobody checks. This
is the point of L-007 applied honestly: the fork is prevented by a gate, not
by wishing. The alternative — teaching the Dockerfile to copy `roadmap/` —
changes the deployment shape of a tree that Q-018 says may not be the product
at all, and is not taken here.

## S2 · Every competitor claim carrying a figure is backed by MARKET.md

**S2a.** Every `$`-denominated figure anywhere in `LandingView.vue` appears
verbatim in `roadmap/MARKET.md`.

**S2b.** Every competitor cell that carries a `$` figure also names at least
one plan that `MARKET.md` tabulates for that vendor. This is `MARKET.md` §1's
own rule: *"Nothing here should be restated as 'DocuSign costs X' without the
plan name attached."*

**S2c.** Competitor per-seat prices carry the **unit each vendor meters**:
DocuSign per **user**, SignWell per **sender**. `MARKET.md` §1's *"What this
establishes"* paragraph states the difference in terms, and the shipped
SignWell cell states the wrong one.

**S2d.** The envelope-limit row states DocuSign's limit as it is published —
per user, per year, on the named plans — or the row goes. It is corrected,
not dropped: the numbers exist and are cited, so removal would discard true
information. `pumasi-booking` `0d1674d` is the precedent for removing a claim
that *cannot* be sourced; this one can be.

**S2e.** The table carries a visible citation naming the two vendor pricing
pages and the date they were read, scoped to **pricing and limits only**. It
must not read as a blanket source for the table, because one row is not
covered — see S4.

## S3 · The Apache-2.0 claim is untouched

The three strings at `LandingView.vue:35`, `:72` and `:194` are byte-identical
to `10a523d`. This is Q-021 and it is the steward's. A-004 proves it.

## S4 · What is left standing, named rather than hidden

The comparison row **"Multi-Tenant Brand Customization"** asserts
*"Enterprise tier only"* (DocuSign) and *"Business tier only"* (SignWell).
These are uncited competitor claims and `MARKET.md` backs neither: its §1 is
pricing and limits only, and it says in terms that *"feature-matrix work
[is] not here yet"*.

They are **not** removed here, for two reasons. The product manager scoped
this packet to (a) and (c) after reading the page line by line, and this row
is neither; and removing a row is a content decision on a marketing surface
whose owner is the product manager and the marketing manager, not this seat.
It is escalated in the return line and the digest instead, so the next
evaluation meets it rather than rediscovers it. **This spec therefore does
not claim that the page carries no uncited competitor claim — only that it
carries no unbacked competitor figure.**

## S5 · Out of scope, stated so a reviewer can hold it

`LICENSE` (Q-021) · deploying (Q-012) · `roadmap/**` · `backend/**` ·
`service/**` and its CI job (Q-018, backlog item 2) · PR-1's version number
(backlog item 6) · `pumasi/catalog.json` (Q-019).

**One exception, and it is a gate adapter, not a feature.** A root
`package.json` is added so that `pumasi/tools/gate.sh` — whose step 1 runs
`npm test` at the repository root — runs this repository's real suite instead
of failing on a missing file. It follows `pumasi-tunnel/package.json`
verbatim in shape: `private`, no dependencies, a `description` that says why
it exists, and **no `version` field**, because the version is PR-1 and
`BACKLOG.md` item 6, and taking it here would be taking the product manager's
next item. The file says so.

---

## Frozen acceptance cases

Six cases. Each names the clause it exercises and the mutation that turns it
red; every mutation was run (L-006) and the evidence is in the commit.

| # | Case | Clause | Goes red when |
| :-- | :--- | :--- | :--- |
| **A-001** | `STAGE` equals the stage on `roadmap/STAGE.md`'s `**Current stage:**` line | S1c | the constant or the register moves without the other |
| **A-002** | `LandingView.vue` contains **zero** stage words; `stage.ts` contains **exactly one**, in the `STAGE` assignment | S1a, S1b | any stage word is hand-written in the view, or a second one appears in `stage.ts` (e.g. a hard-coded badge) |
| **A-003** | every `$` figure in `LandingView.vue` appears verbatim in `MARKET.md` | S2a | `$25`/`$65` return, or any new figure lands without `MARKET.md` |
| **A-004** | every competitor cell carrying a `$` names a plan `MARKET.md` tabulates for that vendor, and states that vendor's own meter word | S2b, S2c | the shipped `"$10 – $30 / user / mo"` returns — no plan name, and `user` where `MARKET.md` says `sender` |
| **A-005** | the three Apache-2.0 strings are byte-identical to `10a523d` | S3 | this packet edits (b) |
| **A-006** | *(e2e, rendered)* `/` served to a signed-out visitor shows the register's badge, shows no `BETA`, and every money figure in the rendered comparison table appears in `MARKET.md` | S1b, S1d, S2a | the page renders a stage or a price the repository cannot back |

**A-004's plan names and A-003's figures are parsed out of `MARKET.md` at
test time.** Neither is written into the test, so neither can fork from the
file it is checking (L-007). The two meter words in A-004 *are* named in the
test, with the `MARKET.md` sentence that establishes them quoted at the
assertion — that pair is the factual error being closed, so it is asserted
rather than derived.

**A-005 retires with Q-021.** Whichever way that entry lands — the `LICENSE`
file, or the claim's removal — the answer changes these strings, and this
case must be updated or deleted in the same commit. It exists to prove this
packet left (b) alone, not to pin the steward's answer.

**Where each runs.** A-001 – A-005 are `vitest` (`frontend` CI job, and the
local gate). A-006 is Playwright (`e2e` CI job). No suite here runs the
deployed tree — `service/` has no CI job at all, which is Q-018 and item 2.
