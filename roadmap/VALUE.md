# VALUE — who this is for, and why they would choose it

**Owned by the product-manager role** ([`pumasi-ops/roles/product-manager.md`](https://github.com/pumasi-ai/pumasi-ops/blob/main/roles/product-manager.md), duty 2).
First pass 2026-08-31, written against `main` @ `5cb3bf8` and the live host.

**Every claim here carries what would falsify it.** A claim without a falsifier
is marketing; this file is evidence. Kept current with releases — a value
proposition that lags the product is the drift this project keeps paying for
([L-007](https://github.com/pumasi-ai/governance/blob/main/lessons/L-007-restating-a-rule-forks-it.md)).

**Two things a reader must know before the claims.**

1. **The stage is [`alpha`](STAGE.md)**, not `beta`, whatever the chip on the
   landing page says. Nothing below is a promise to a stranger yet.
2. **Claims are grounded in the tree that serves users** — the Cloudflare
   Worker in `service/`, which is what `sign.pumasi.ai` runs. The FastAPI app
   in `backend/` implements the same product and is not in production; which
   one *is* Pumasi Sign is open as `pumasi/DECISIONS.md` **Q-018**. Where a
   claim is grounded only in `backend/`, it is not made here.

Competitor facts come from [`MARKET.md`](MARKET.md), cited and dated. No
competitor number appears in this file that is not in that one.

---

## 1 · Who it is for

**The team that sends the same three documents over and over.** Offer letters,
NDAs, contractor agreements, consent forms. They already know exactly what a
signature workflow looks like — they are not shopping for a category, they are
tired of paying per seat for one. Template creation, reusable field placement
and a per-envelope status list are the whole of what they need.

**The sender who hit the envelope ceiling.** DocuSign's two mainstream business
plans state a limit of 100 envelopes per user per year at $30 and $45 per user
per month ([`MARKET.md` §1](MARKET.md)). The person this product is for is the
one who found that out in month eleven. Here there is no meter: the deployed
service contains no quota, plan, billing or subscription code at all — a `grep`
over `service/src` for `quota|plan|billing|stripe|subscription` returns nothing
but rate-limiting.

**The organisation that wants its own name on the envelope without an upgrade.**
Company name, logo and primary colour are per-owner rows in the deployed
service (`service/src/durable.ts:152`, `:808`), applied to what recipients see,
at no tier — because there are no tiers.

**The external signer, who did not choose any of this.** They get a link and an
emailed code, sign in a browser, and never make an account
(`durable.ts:1310` — the access token *is* the identity). This is the largest
population the product touches and the one that never reads a pricing page.

**Not yet: the operator who wants to run it themselves.** The repository is
public but carries **no `LICENSE`** (`gh repo view --json licenseInfo` → `null`,
2026-08-31). Until that is resolved — `pumasi/DECISIONS.md` **Q-021** — a
self-hoster has no grant of rights, and this file does not name them as an
audience. See §4.

**Contested, and named rather than papered over.** `README.md` describes an
internal tool for Pumasi employees; the landing page sells public self-serve
signup; the live worker's `establishSession` (`durable.ts:655`) creates an
account for any verified email address, with no domain gate. Three different
answers to *who may hold an account*, in one product. That is Q-018's second
half, and no claim below depends on which way it lands.

## 2 · The pain

E-signature is bought once and then paid for forever, by the seat, with the
ceiling written where nobody reads it. The features that make it usable for a
team — your logo on the envelope, more than a handful of sends — are the ones
held one tier up. And the cost is not only money: the artifact everyone
downstream actually relies on is *the signed PDF and its certificate*, and that
artifact is produced by a vendor whose code the signer cannot read.

## 3 · The claims, and what would falsify each

**C1 — A signed document comes back with a cryptographic record of what was
signed, on every envelope, at no tier.** `stampAndCertifyPdf`
(`service/src/core/stamping.ts`) hashes the original bytes with SHA-256 before
stamping (`:52`), draws the digest onto an appended certificate page (`:199`),
and hashes the completed output (`:278`). It runs on the completion path
(`durable.ts:1570`), not behind a flag.
*Falsified by:* one completed envelope whose stored PDF has no certificate
page; one certificate whose printed digest does not match `sha256sum` of the
file it claims to describe; any tier or setting that turns it off.

**C2 — No meter, no seat, no upgrade path.** See §1. There is nothing in the
deployed service to bill with.
*Falsified by:* any envelope, template, branding or recipient count that
refuses work on quantity; any code path that reads a plan; a
commercialization decision that moves a feature named in this file behind
payment.

**C3 — A recipient signs without an account, from an email.** Token link plus
an emailed verification code; no login, no password, no signup for the person
who only has to sign.
*Falsified by:* an external recipient being asked to create an account, set a
password, or verify a domain in order to complete a signature.

**C4 — Your organisation's identity, not the vendor's, on what the recipient
sees.** Per-owner company name, logo and colour (§1), defaulting to
`Pumasi Sign` / `#1A56DB` when unset (`durable.ts:813`).
*Falsified by:* branding that a recipient never sees; branding gated on
anything.

**C5 — The whole thing runs on one edge service you could point at your own
account.** `service/` is a single Cloudflare Worker with a Durable Object store
and R2 for documents; `npm run deploy` is `wrangler deploy`. No Kubernetes, no
database server to operate.
*Today's honest limit, and it is the sharp one:* **there is no licence**, so
"you could" is an architectural statement, not a legal one. This claim is
**suspended** until Q-021 resolves — it may not be used in public copy before
then, and the landing page's current "Apache-2.0 (Open Source)" row is
[`BACKLOG.md`](BACKLOG.md) item 1.
*Falsified by:* a deployment that needs a component not in this repository; a
resolved Q-021 that declines to license the code.

**C6 — What the incumbents do at the top of their price list, this does at the
bottom.** The comparison is `MARKET.md` §1 and only §1: unlimited envelopes
against a stated 100/user/year on DocuSign Standard and Business Pro; per-owner
branding against plans that do not list it; senders metered by SignWell's paid
tiers against no sender concept here.
*Falsified by:* any of `MARKET.md`'s cited rows changing on the vendors' own
pages without this file being updated — which is the failure mode this
project is built to notice.

## 4 · What this file does not claim, on purpose

- **Not "open source."** No licence (§1, C5).
- **Not "beta," and not "reliable for strangers."** [`STAGE.md`](STAGE.md) §2
  lists five reasons, the largest being that the deployed tree carries two
  tests and no CI gate.
- **Not a QES / eIDAS-qualified signature.** The product produces an advanced
  electronic signature with a hash-based audit certificate; qualified
  signatures need hardware the product does not touch. (The landing page states
  this correctly today and should keep doing so.)
- **Not "your data is safe forever."** There is no stated retention or backup
  posture for the Durable Object store and R2 to cite. `STAGE.md` §2.4.
- **Nothing about a competitor that is not in `MARKET.md` with a source and a
  date.**

## 5 · How this file gets checked

At every product evaluation (role duty 4): does the release just shipped
deliver a claim above, and does any claim now have a live falsifier? A claim
that acquires one is *demoted in this file in the same commit that finds it* —
the same rule `STAGE.md` runs on.
