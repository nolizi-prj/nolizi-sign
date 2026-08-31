# SPEC · 0004 — the deployed tree's front door, recorded

**Intent:** [`INTENT.md`](INTENT.md) · **Backlog:** item **1**, first slice
**Frozen:** at spec review, before implementation.

The rules this change is measured against are not restated here (L-007):
`pumasi/governance/CHARTER.md` (Part 0, Part 3), `pumasi/DECISIONS.md`
**Q-012**, **Q-018**, **Q-021**, **Q-025**, **Q-027**, **Q-028**,
`pumasi/lessons/L-006`, `L-007`, `L-009`, `pumasi/governance/DEBT.md` **D-104**.

**Case numbering.** `spec/0001` owns **A-001 – A-006**, `spec/0002` owns
**A-100 – A-109**, `spec/0003` owns **A-200 – A-208**; all keep running. This
spec numbers from **A-300**.

**Risk class: ordinary, not can-hurt.** Stated with the reasoning rather than
asserted, because this repository has no `RISK_ZONES.yaml` and the class is
this spec's call. The change adds two files under `service/src/test/` and
edits nothing that the worker bundles: `wrangler deploy` would upload a
byte-identical worker before and after. It touches no money, no credential and
no personal datum; it opens no network socket and writes no file outside the
process (§S3c). It cannot reach a user, so there is nothing for a 7-day window
to protect and CHARTER §4's can-hurt gate does not apply. What it *can* do is
mislead a reader of a test count — which is L-006, and which §S4 is entirely
about.

---

## S1 · The harness — what it is, and what it must not be read as

`service/`'s suite runs under `node --test`, not under `workerd`, so
`DurableObjectState.storage.sql` does not exist in it. `PumasiSignService`'s
constructor takes `state.storage.sql` and nothing else from the platform
(`durable.ts:110`).

**S1a.** `service/src/test/support/durable-harness.ts` supplies exactly that:
a `SqlStorage`-shaped object backed by `node:sqlite`'s in-memory
`DatabaseSync`, wrapped in a fake `DurableObjectState`, plus a `fetch(path,
init)` helper that drives the object through its **own `fetch()` entrypoint**
— the same one `worker.ts` calls — rather than through any private method.

**S1b. No new dependency, and no I/O.** `node:sqlite` is in the standard
library of the Node the suite already runs on (`22`, in CI and locally). The
harness adds nothing to `service/package.json`. Mail is left **unconfigured**
(`mailConfigured` is false without `GMAIL_SA_KEY` and `MAIL_IMPERSONATE`), so
no case can reach `sendMail`; verification codes are seeded straight into
`auth_codes` through the harness's own database handle.

**S1c. The seam is the storage boundary, and that is the honest limit.** This
is SQLite, but it is not `workerd`'s SQLite. A case here is evidence about
`durable.ts`'s own logic — its SQL, its branching, its response shapes — and
not about Cloudflare's storage engine byte for byte. Where the two could
diverge (value coercion at the boundary, statement limits) a green case here
proves the code, not the platform. **This is written into the harness's own
docblock as well as here**, because the failure this whole spec exists to
avoid is a reader over-reading a count.

**S1d. `node:sqlite` is imported unconditionally and is never skipped.** A
`describe.skip`-on-missing-module would convert a broken harness into a silent
green — L-006 exactly. If the module ever stops being importable, every case
in `auth-session.test.ts` goes **red**.

### The trap inside the harness, which is why A-300 exists

`workerd`'s `sql.exec` accepts a **multi-statement** block; `initSchema`
(`durable.ts:114`) passes one containing twelve `CREATE TABLE` statements.
`node:sqlite` splits that job in two: `db.exec` runs many statements and
returns nothing, `db.prepare(q).all()` runs **one** and returns rows.

**The first draft of this harness tried `prepare` first and fell back to `exec`
on throw. `node:sqlite`'s `prepare` does not throw on a multi-statement
string — it silently keeps the first statement.** Measured during
construction: the database came up with exactly **one** table, `users`, and
every case that only signed in and read `/api/auth/me` would still have
passed. That is this spec's own L-006 near-miss, it is recorded rather than
sanded off, and **A-300 is the case that would have caught it**.

## S2 · What is characterized — `establishSession` and the cookie it mints

**S2a.** Signing in through the served tree's own route
(`POST /api/auth/login/verify`, `durable.ts:798`) returns **200**, creates a
`users` row, and sets a `sign_session` cookie; presenting that cookie to
`GET /api/auth/me` returns **200** and the same account.

**S2b.** `establishSession` creates an account for a verified email at **any**
domain. **Recorded, not endorsed** — see §S4.

**S2c.** It is **find-first**: a second sign-in for the same address reuses the
existing `users` row, mints an **additional** session, and does **not** update
the stored display name or provider from the newer sign-in. The
`org_branding` row is created on first sign-in only.

**S2d.** The address is normalised to lower case before both the code check and
the account lookup, so `MiXeD@Pumasi.AI` matches a code issued for
`mixed@pumasi.ai` and does not create a second account.

**S2e.** The display name on the email path is taken from the request body when
present and otherwise derived from the local part (`first.last` → `First
Last`). **It is neither trimmed nor length-capped**, unlike the OAuth path,
which caps at 120 characters (`durable.ts:769`). Recorded; proposed as a
backlog entry in §S6, not repaired here.

**S2f.** Session validation admits a live token and nothing else: no cookie,
an unknown token, and a session whose `expires_at` has passed are each
**401 `Not signed in`**. `POST /api/auth/logout` deletes the presented token
and clears the cookie, after which that token is 401.

**S2g.** The minted cookie is 64 lower-case hex characters (32 random bytes)
and carries `Path=/`, `HttpOnly`, `Secure`, `SameSite=Lax` and
`Max-Age=2592000` (30 days).

**S2h.** Account creation is behind the code check: a wrong code, an expired
code, and a code issued for a different address each return **401** and leave
`users` and `sessions` empty. A correct code is **single-use** — replaying it
returns 401.

**S2i.** Sessions are **not** rotated or reaped: a cookie minted before a later
sign-in stays valid, and an expired session's row is not deleted when it is
rejected. Recorded; proposed in §S6, not repaired here.

**S2j.** The identity `/api/auth/me` reports is workspace-scoped and constant:
every session holder is `is_admin: true`, `is_external: false`,
`can_send: true`, and those three are literals in the response rather than
columns (`durable.ts:823`; the `users` table has no such columns). Recorded —
this is the same Q-018 divergence as S2b seen from the other end, and §S4
governs it.

## S3 · What the cases must not do

**S3a.** No case edits, imports for mutation, or monkey-patches any file that
ships to the worker. `durable.ts` is imported and constructed; that is all.

**S3b.** No case reaches a private method. Everything goes through `fetch()`,
or through the harness's own database handle for seeding and reading back.

**S3c.** No case performs network or filesystem I/O. The database is
`:memory:`; mail is unconfigured; no `fetch` beyond the Durable Object's own.

**S3d.** Each case constructs a **fresh** harness. No case depends on another's
state or on execution order.

## S4 · The Q-018 boundary, in the cases themselves

**S4a.** The cases that record the account-creation rule (**A-302**) and the
reported identity (**A-308**) each carry, at the assertion, a comment naming
`pumasi/DECISIONS.md` **Q-018**, stating that `backend/` gates on
`ALLOWED_EMAIL_DOMAINS` and the worker does not, and stating that **the day a
steward answers Q-018 in `backend/`'s favour, these cases going red is the
correct outcome and not a regression.**

**S4b.** No case asserts that either rule is the right one, and no case name
uses a word of approval or disapproval. A characterization case whose red
means *"someone decided"* rather than *"someone broke it"* is only safe if it
says which, and these say it.

**S4c.** Nothing in this change deletes a tree, re-points a domain, moves data,
or edits `CLAUDE.md`'s account of either implementation.

## S5 · Where the slice stops, and the coverage it does not claim

Taken: sub-item **1** (`establishSession`) and sub-item **2** (session
validation). **Not taken: sub-item 3, envelope state transitions** — the slice
is coherent at *sign in, and what the cookie admits*, and stopping there is the
packet's own instruction rather than an omission.

Two limits are **stated** rather than left to be discovered:

- **The OAuth branch of `establishSession` is not characterized.**
  `durable.ts:770` reaches the same function after exchanging a code at the
  provider's token endpoint; a case would have to stub that endpoint. Only the
  email branch (`:807`) is covered here. So a green A-301 is evidence about one
  of the two callers, not both.
- **`worker.ts`, `storage/r2.ts`, `mail.ts`, `feedback.ts`,
  `convert/graph.ts`** remain covered by nothing, and every non-auth route of
  `durable.ts` remains covered by nothing. This change moves the number the
  gate prints; it does not make the tree well covered, and no release note or
  stage claim may read it as doing so.

## S6 · Found while characterizing — proposed, not taken

Three, recorded here and offered to the product manager in the return block.
**None is patched in this commit**, because item 1's boundary says a defect
found while characterizing becomes a backlog entry rather than a repair riding
in a test packet.

1. **The email sign-in path stores an untrimmed, uncapped display name from the
   request body** (§S2e). `durable.ts:807` does `String(body.name || …)` with
   no `.slice()`; the OAuth path one branch above caps at 120. The value is
   persisted in the Durable Object's SQLite and echoed back by `/api/auth/me`.
   This is a divergence *inside* the worker, not across the two trees, so
   proposing it is not adjacent to Q-018.
2. **Sessions are neither rotated on sign-in nor reaped on expiry** (§S2i).
   Every sign-in appends a row that lives 30 days; a rejected expired session
   is left in the table. Modest, and it is the kind of thing that is cheap now.
3. **The suite runs on `node --test` against a SQLite shim, not on `workerd`**
   (§S1c). `@cloudflare/vitest-pool-workers` would run these same cases on the
   real runtime. It is a whole packet, not a side errand: it replaces the
   runner whose TAP counts `.github/scripts/assert-service-suite-ran.sh` reads,
   and that guard is pinned by frozen **A-103**, **A-104** and **A-207**.

## S7 · Out of scope, stated so a reviewer can hold it

Every `service/src` file that ships to the worker · `backend/**` ·
`frontend/**` · `.github/**` and the root `package.json` (and so **A-208**,
untouched — `BACKLOG.md` item 4 is not taken in passing) · `roadmap/**`, the
product manager's · **deploying (Q-012, Q-018)** · `LICENSE` and
`LandingView.vue` (Q-021, Q-028) · `pumasi/catalog.json` (Q-019) ·
`pumasi/HUMAN.md` · `web/` and `pumasi-web` ·
`reviews/20260831-143359-code-qwen.md`, which this packet may not commit, edit
or delete.

---

## Frozen acceptance cases

Nine cases, in `service/src/test/auth-session.test.ts`. They are **new
coverage of unchanged code**, so "red against the change-absent tree" is not a
meaningful column — at `38ba661` the file does not exist and neither does the
harness. The column that carries the weight is the last one: **the single
mutation that turns the case red**, applied to the tree under test and then
reverted. Every mutation was run; the evidence is in the implementation
commit.

| # | Case | Clause | Single mutation that turns it red | Measured — every mutation below was applied, built and run, then reverted |
| :-- | :--- | :--- | :--- | :--- |
| **A-300** | the harness runs the **whole** of `initSchema`, not its first statement: all twelve declared tables exist, the `ALTER TABLE` migration columns are present on `submitters`, and an unknown route answers through the same `fetch()` with the worker's own `404` body | S1a, and the near-miss in §S1 | **two, both run.** *M-300*: restore the harness's first draft — try `prepare().all()` before `exec()` for a no-binding statement. *M-300b*: build only the four tables the other eight cases touch | M-300 → `pass=2 fail=9`, every case red (a harness with one table breaks everything). **M-300b → `pass=10 fail=1`, A-300 alone red** — that is the isolating one, and it is what makes A-300 a guard rather than a duplicate |
| **A-301** | `POST /api/auth/login/verify` with a live code returns 200, creates the account, sets `sign_session`, and that cookie is what `GET /api/auth/me` accepts, for the same id and email | S2a | `establishSession` returns a cookie naming a token it never inserted into `sessions` | `pass=8 fail=3` — A-301, A-306, A-308 |
| **A-302** | **recorded, not endorsed:** a verified email at a domain other than `pumasi.ai` is admitted and an account is created for it — the Q-018 divergence, and red here means a steward answered, not that something broke | S2b, S4a | add an `ALLOWED_EMAIL_DOMAINS`-style gate to `establishSession`, which is what answering Q-018 the other way would do | `pass=10 fail=1` — A-302 alone |
| **A-303** | find-first: a second sign-in reuses the `users` row, does **not** overwrite the stored name or provider, mints a second session, and leaves exactly one `org_branding` row | S2c | make `establishSession` `UPDATE users SET name = ?` when the row already exists | `pass=10 fail=1` — A-303 alone |
| **A-304** | mixed-case input normalises: signing in as `MiXeD@Pumasi.AI` against a code issued for `mixed@pumasi.ai` succeeds and leaves one account, stored lower-cased | S2d | drop `.toLowerCase()` from the verify route's email parse | `pass=10 fail=1` — A-304 alone |
| **A-305** | the display name is taken from the body when given — **verbatim, untrimmed and uncapped** — and otherwise derived from the local part, `first.last` → `First Last` | S2e | apply `.trim().slice(0, 120)` to the email path's `displayName`, as the OAuth path already does | `pass=10 fail=1` — A-305 alone |
| **A-306** | the cookie admits a live token and nothing else: absent → 401, unknown → 401, expired row → 401, and `POST /api/auth/logout` deletes the presented token and clears the cookie | S2f | drop `AND s.expires_at > ?`, and its binding, from `sessionUser`'s query | `pass=9 fail=2` — A-306, A-308 |
| **A-307** | account creation is behind the code check — wrong code, expired code, and a code issued for another address each return 401 leaving `users` **and** `sessions` empty — and a correct code is single-use | S2h | make `consumeCode` return `true` when no row matched | `pass=10 fail=1` — A-307 alone |
| **A-308** | the minted cookie is 64 hex characters with `Path=/`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Max-Age=2592000`; sessions are neither rotated nor reaped; and **recorded, not endorsed**, `/api/auth/me` reports `is_admin`/`can_send` true and `is_external` false for every account (Q-018, §S4a) | S2g, S2i, S2j, S4a | remove `HttpOnly` from `setCookie` | `pass=10 fail=1` — A-308 alone |

**Method, so the column can be checked rather than believed.** Each mutation
was applied to the working tree, `npm run build` re-run, `npm test` re-run, the
`not ok` lines and the `# pass`/`# fail` summary read from the runner's own
output, and the file restored from a copy taken before the edit.
`git diff service/src/durable.ts` is empty in the commit that carries this
spec: **no shipped worker file is modified by this change.**

### Why A-300 is not decorative

It is the reader guard, the analogue of `spec/0002`'s A-100 and `spec/0003`'s
A-200. Every other case in this file reaches at most four tables — `users`,
`sessions`, `auth_codes`, `org_branding`. A harness that built only those
would leave all eight of them green while the object it claims to construct was
never really constructed. A-300 asserts the harness reached the **whole**
schema and that the object routes, so that the other eight are assertions about
`durable.ts` rather than about a stub.

**Its mutations are not hypothetical, and the second one is the proof.** M-300
is the bug this harness actually had. M-300b is the sharper one: a harness that
builds `users`, `sessions`, `auth_codes` and `org_branding` and nothing else
leaves **all eight** other cases green — `pass=10 fail=1`, A-300 alone red.
That is the exact hole this case exists to fill, measured rather than argued.

### What these cases do **not** claim

They do not claim `service/` is covered. They cover one function and one
cookie, on one of that function's two callers, through a SQLite shim rather
than `workerd` (§S1c, §S5). They move the number
`.github/scripts/assert-service-suite-ran.sh` prints from **2** to a larger
one, and the number is still small. The next slice is sub-item 3 — envelope
state transitions — and after it, the OAuth caller.
