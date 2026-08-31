# INTENT · 0001 — the landing page states the stage it has and the prices it can cite

**Date:** 2026-08-31
**Source:** `roadmap/BACKLOG.md` item 1, halves **(a)** and **(c)** only.
**Repository:** `pumasi-sign`. Touches `frontend/` only.

## What is wrong

`frontend/src/views/LandingView.vue` was merged at `10a523d` and is **not
deployed** — the live bundle `https://sign.pumasi.ai/assets/index-j38Qwibz.js`
was fetched at HTTP 200 on 2026-08-31 (839 941 bytes) and contains zero
occurrences of `landing`, `BETA`, `DocuSign` or `Apache-2.0`. That is the only
reason the two defects below are questions and not incidents.

**(a) The page announces a stage the product does not have.** The file ships a
`BETA` chip, a banner reading "Pumasi Sign is in active Beta", and a header
comment describing the "current Beta stage" — three hand-written copies of one
label. [`roadmap/STAGE.md`](../../roadmap/STAGE.md) records **`alpha`**, set
2026-08-31 on measured evidence, and names this disagreement in its §5 with
the coder as the owner of the fix. `pumasi-ops/STAGE_PLAYBOOK.md`'s Stage-1
Surface B deliverable asks for a prominent `[ALPHA - ACTIVE DEVELOPMENT]`
badge. The chip contradicts both.

**(c) The comparison table asserts competitor prices that are wrong.**
The table claims DocuSign at "$25 – $65 / user / mo", SignWell at
"$10 – $30 / user / mo", and DocuSign at a "100 / yr hard cap", with no
source. [`roadmap/MARKET.md`](../../roadmap/MARKET.md) §1, read from each
vendor's own pricing page on 2026-08-31 and cited with URLs and that date,
records DocuSign at **$11 / $30 / $45** per user per month (Personal /
Standard / Business Pro) and SignWell at **$10–$12** per **sender** per month
— the meter is senders, not users, and SignWell's paid tiers state *unlimited*
documents. DocuSign's 100-envelope limit is **per user per year on two named
plans**, which is not "100 / yr hard cap". `MARKET.md`'s own §1 forbids
restating a figure "without the plan name attached", and the product-manager
role forbids an uncited competitor claim *ever*. This project has already
published and retracted one (`pumasi-booking` `0d1674d`).

## What this change does

Makes the page say what the repository can back, in both places, reading each
fact from **one** source (L-007) rather than restating it.

## What this change deliberately does not do

- **(b), the Apache-2.0 claim** at `LandingView.vue:35`, `:72` and `:194`.
  `ls LICENSE` fails here and `gh repo view pumasi-ai/pumasi-sign --json
  licenseInfo` returns `null` — the claim is untrue today. It is
  `pumasi/DECISIONS.md` **Q-021** and it is the steward's both ways: adding
  the file is an outward grant a third party may rely on, and removing the
  claim is the entry's named alternative with a cost listed in three places.
  All three strings are left byte-identical, and acceptance case **A-004**
  exists to prove it.
- **(d), the deploy.** `pumasi/DECISIONS.md` **Q-012** is open and explicitly
  outside CHARTER Part 0's proceed-on-default rule. No `wrangler deploy`. The
  same deploy would also carry ~5 commits of unreviewed UX change and all of
  (b).
- **`roadmap/`.** `BACKLOG.md`, `STAGE.md`, `VALUE.md` and `MARKET.md` are the
  product manager's, written at `6e02cc4`/`d797c81`. Read, not edited.
- **`backend/` and `service/`.** Which of them is the product is **Q-018**;
  this change touches neither, so it does not act on that question. The
  `service/` CI job is `BACKLOG.md` item 2 and a different packet.

## Who this can cost

Nobody today: the page is undeployed. When it is deployed, a visitor reads
`ALPHA — ACTIVE DEVELOPMENT` instead of `BETA` — a weaker claim than the one
being replaced, which is the direction that cannot hurt — and reads
plan-qualified competitor prices that each vendor could check against their
own published page on the date given.
