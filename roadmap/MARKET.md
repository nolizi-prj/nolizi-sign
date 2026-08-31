# MARKET — the competitors, and what is actually true about them

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 3).
First pass 2026-08-31.

**Every claim about a competitor is cited or absent.** No exceptions, ever —
this project has already published and then removed one uncited competitor
claim (`pumasi-booking` `0d1674d`). Fairness rule: write about them honestly
enough that they could read this page without objecting to a fact.

**This is a first pass**, deliberately narrow: it covers what
[`VALUE.md`](VALUE.md) needs to make a comparison, and what
[`BACKLOG.md`](BACKLOG.md) item 1 needs to correct a public page. Positioning,
funnel and feature-matrix work are not here yet.

The two named comparators are the ones `pumasi/catalog.json` records for this
product: **DocuSign** and **SignWell**.

---

## 1 · Published pricing

Read from each vendor's own public pricing page on **2026-08-31**. Prices
move; the date is part of the claim, and a reader who finds different numbers
should update this file rather than argue with it.

### DocuSign eSignature
Source: <https://ecom.docusign.com/plans-and-pricing/esignature>, fetched
2026-08-31.

| Plan | Price as shown | Envelope limit as shown |
| :--- | :--- | :--- |
| Personal | $11/month (annual, billed monthly; $132/yr) | 5 per month |
| Standard | $30/user/month (annual, billed monthly; $360/yr per user) | 100/user/year |
| Business Pro | $45/user/month (annual, billed monthly; $540/yr per user) | 100/user/year |
| Enhanced Plans | not shown — contact sales | "Custom limit" |

### SignWell
Source: <https://www.signwell.com/pricing/>, fetched 2026-08-31.

| Plan | Price as shown | Document limit as shown |
| :--- | :--- | :--- |
| Free | $0 | 3 documents a month, 1 sender |
| Light | $12/sender/month, or $10/sender billed annually | Unlimited documents |
| Business | $36/month for 3 senders, or $30 billed annually; additional senders $15/mo or $12/yr | Unlimited documents |
| Enterprise | custom | Unlimited documents |

### What this establishes, and what it does not

**Establishes:** both vendors sell per-sender subscriptions; DocuSign's two
mainstream business plans state a **100 envelopes per user per year** limit at
$30 and $45 per user per month; SignWell's paid tiers state unlimited
documents and meter **senders** rather than documents.

**Does not establish:** any claim about discounts, enterprise contracts,
regional pricing, or what a given buyer actually pays. Nothing here should be
restated as "DocuSign costs X" without the plan name attached.

### A correction this file forces

`frontend/src/views/LandingView.vue` (merged `10a523d`, **not yet deployed**)
asserts, uncited, "DocuSign: $25 – $65 / user / mo" and "SignWell: $10 – $30 /
user / mo". Against the pages above on this date, both ranges are wrong at both
ends. The envelope-limit row ("100 / yr hard cap") is close but drops the
per-user qualifier and the plans it applies to. Correcting or removing that
table before the page reaches the public is [`BACKLOG.md`](BACKLOG.md) item 1;
it is product code, which this role may not edit.

## 2 · How they are delivered

Both DocuSign eSignature and SignWell are sold on the pages above as hosted
subscriptions. **Neither pricing page offers a self-hosted or source-available
option**, and no plan row on either page mentions source access. That is the
whole of what is claimed here about their licensing — this file does not
characterise their terms of service, which it has not read.

Pumasi Sign's repository is public (`github.com/pumasi-ai/pumasi-sign`,
`visibility: PUBLIC`). **It carries no `LICENSE` file today** — `gh repo view
--json licenseInfo` returns `null` — so "open source" is not yet a difference
this product may claim, whatever the landing page says. See
[`STAGE.md`](STAGE.md) §2.3 and `pumasi/DECISIONS.md` **Q-021**.

## 3 · The wedge, stated as a hypothesis

Not a finding — a hypothesis this file exists to test as evidence arrives:

> The buyer who resents the category is not the one who cannot afford $30. It
> is the team that discovers, in month eleven, that "unlimited e-signature" was
> 100 envelopes per user per year, and that the branding they wanted is one
> tier up. The wedge is **no meter and no tier**, on a codebase they can read.

The third clause of that sentence is not currently true (§2). Until it is, the
wedge is two clauses wide, and [`VALUE.md`](VALUE.md) says so.
