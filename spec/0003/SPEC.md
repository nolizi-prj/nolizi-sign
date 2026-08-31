# SPEC · 0003 — the way back in, and a gate that ran the tree it is read as covering

**Intent:** [`INTENT.md`](INTENT.md) · **Backlog:** items **1** and **2**
**Frozen:** at spec review, before implementation.

The rules this change is measured against are not restated here (L-007):
`pumasi/governance/CHARTER.md` (Part 0, Part 3), `pumasi/DECISIONS.md`
**Q-012**, **Q-017**, **Q-018**, **Q-019**, **Q-021**, **Q-025**,
`pumasi/PRODUCT-RULES.md` (v1.0, readable only on branch
`worktree-product-rules` `0115758` — that is Q-017, and absence from `main` is
not compliance), `pumasi/lessons/L-006`, `L-007`, `L-009`.

**Case numbering.** `spec/0001` owns **A-001 – A-006** and `spec/0002` owns
**A-100 – A-109**; both keep running. This spec numbers from **A-200**.

---

## S1 · The way back in — and why this repair and not the other

`roadmap/BACKLOG.md` item 1 names two candidate repairs and leaves the choice
to this spec, because the choice decides which tree the change lands in.

**Chosen: repair 1 — the button targets the SPA's own `/login` page**, via the
existing `loginPageUrl` helper.

**Rejected: repair 2 — add `GET /api/auth/login` to the worker.**

Four reasons, in the order they carry weight:

1. **The destination already exists and already works on the served tree.**
   Verified against `sign.pumasi.ai` at `2bd3ba7`: `GET /login` → **200
   `text/html`** (`wrangler.jsonc` sets
   `not_found_handling: single-page-application`). And every call
   `LoginView.vue` makes is a worker route: `POST /api/auth/login/request`
   (`durable.ts:775`), `POST /api/auth/login/verify` (`:798`), and
   `GET /api/auth/oauth/{google,microsoft}` (`:699`) — the last two probed
   live and both answer **302**, so both SSO buttons on that page are
   configured on the deployment, not merely present in the markup. Repair 1
   sends the user to a page this product already serves and already supports.
   Repair 2 would add a worker route whose entire content is a redirect to
   that same page, bought with a network round trip.

2. **It leaves one expression in the frontend for "send this browser to sign
   in", not two.** `loginPageUrl` is what `http.ts`'s own `401` interceptor
   already uses (`:41`–`:44`). `loginRedirectUrl` sits twelve lines above it
   and has exactly one caller — `SignedOutView.vue`. Repair 2 keeps both
   alive, and keeps the one that is a trap: a function named for the obvious
   job, producing a URL that only one of the two trees answers. Two functions
   for one job is L-007's shape in code, and this repair deletes one of them.

3. **It is neutral to Q-018; repair 2 is not.** Which tree *is* Pumasi Sign is
   open and is the steward's. Repair 1 works identically on both trees:
   `backend/` also serves the SPA and also has a `/login` route, and
   `backend/app/routers/auth.py:82` is left untouched for anything else that
   wants it. Repair 2 would grow the worker's API surface specifically to
   mirror `backend/`'s — a decision about the shape of the deployed tree,
   taken by a coder packet, adjacent to a question reserved above it.

4. **A full-document navigation is the right semantics here and is
   preserved.** The user has just signed out; a fresh document load is the
   surest way to start their next session with no stale client state. Repair 1
   keeps the `:href` and changes only where it points.

**One more edit inside `http.ts`, in scope and named.** That file's own opening
docblock says the SPA's API is *"served by the same FastAPI app that serves the
built SPA (see `backend/app/main.py`'s SPA fallback)"*. That sentence is how
this bug was written: it tells the next author that `backend/`'s routes are the
routes. It is corrected to name the worker, `run_worker_first`, and Q-018.
Nothing else in the file's behaviour changes, and no claim about which tree
*is* the product is made — only about which tree answers `/api/*` today, which
is measured (`sign.pumasi.ai` returns the worker's error body, not FastAPI's
`{"detail": …}`).

**The cost of repair 1, stated rather than discovered.** On `backend/`,
*Sign in again* currently jumps straight into the Entra flow; after this
change it lands on the SPA login page, one click from the same place
(*Continue with Microsoft*). That is one extra click **on a tree no user
reaches**, and it is the same page `http.ts`'s interceptor already sends every
401 to. `SignedOutView.vue`'s own copy — *"You're still signed in to Microsoft
in this browser, so signing in again won't ask for a password"* — stays true,
because that button is on the page the user now lands on.

**S1a.** `frontend/src/views/SignedOutView.vue` computes its *Sign in again*
target with `loginPageUrl` imported from `../utils/http`, and does not import
or call `loginRedirectUrl`.

**S1b.** No source file under `frontend/src/` that ships to a browser
constructs a navigation target under `/api/auth/login`. The sub-paths
`/api/auth/login/request` and `/api/auth/login/verify` are live worker routes
and are **not** what this clause forbids; the clause is about the bare path,
which no tree that serves users answers.

**S1c.** The destination is real: resolving `loginPageUrl("/")` through this
application's own router yields the route named `login`, and that route is
reachable without a session.

### One test seam, named rather than slipped in

S1c says *through this application's own router*, and that requires a seam.
`frontend/src/router/index.ts` calls `createWebHistory()` at module scope,
which needs `document`; vitest runs this repository's unit suite in the `node`
environment, with no DOM and no `jsdom` in the tree. So the route table is
moved, unchanged, to `frontend/src/router/routes.ts` and imported back by
`index.ts`, which keeps the history and the navigation guard.

It is a **pure move**: no route is added, removed, renamed or re-`meta`'d, and
`index.ts` behaves identically. It is called out here because it is the one
edit in this change that is neither of the two backlog items, and because the
alternative — asserting the route table by reading `index.ts` as text — would
have made A-203 a text case and left this spec with no executing case at all.

## S2 · The gate covers the tree users actually meet

**S2a.** Running `npm test` at this repository's root runs `service/`'s own
test suite, in addition to everything it ran before.

**S2b.** It **builds before it runs**, and it **installs before it builds**.
`service/package.json`'s `test` is `node --test dist/test/*.test.js` — the
compiled tree — and `service/dist/` is `.gitignore`d, so a clean checkout has
none. This is `spec/0002` **A-103**'s premise, unchanged and still asserted
there.

**S2c.** It **cannot report success having run nothing.** After the suite, the
root script invokes **the same guard file** `spec/0002` built and froze —
`.github/scripts/assert-service-suite-ran.sh` — with the same three arguments
`ci.yaml`'s `service` job passes it. Not a second guard, not a copy: the same
file, whose behaviour is already exercised against fixtures by frozen case
**A-104**.

### Why the runner is a committed script and not a longer `test` string

Same reason `spec/0002` §S1 gave for the guard. A sequence that exists only
inside a JSON string can be *string-matched* by an acceptance case and nothing
more, and it cannot capture the suite's output for the guard to read without
`pipefail`, which is not POSIX `sh`. As a file —
`.github/scripts/run-service-suite.sh`, beside the guard it calls — it is
readable, reviewable, and runnable by hand. It lives in `.github/scripts/`
because that is the one directory this repository already keeps committed
check scripts in, and because the guard it wraps is already there.

## S3 · Nothing is bought by shrinking

**S3a.** The root `test` script still runs the frontend unit suite and still
type-checks with `vue-tsc` **`-b`**. `BACKLOG.md` item 2 says *"do not shrink
the frontend half to make room"*; the invariant is asserted, not promised.

**S3b.** The root `package.json` still carries **no `version` field**. That is
`PRODUCT-RULES.md` **PR-1** and `BACKLOG.md` **item 6**, it is the product
manager's next item and not this packet's, and the root `package.json` is
exactly the file a packet in this scope would be tempted to set it in.

**S3c.** `.github/workflows/ci.yaml` still defines `backend`, `frontend`,
`service` and `e2e`. (`spec/0002` **A-109** already asserts three of these; the
`service` job did not exist when that case was frozen, so it is asserted here.)

## S4 · The duplication this change leaves, stated so a reviewer can hold it

After this change, the `service` suite is invoked from two places: the
`service` job in `ci.yaml` (install → build → suite → guard, as four steps)
and `.github/scripts/run-service-suite.sh` (the same four, as one file). The
tidier shape is for the job to call the script.

**It is not taken, and the reason is a rule this seat is under.** `spec/0002`
froze **A-101** (a step whose working directory is `service` runs that
package's `test` script), **A-102** (a build step precedes the suite step) and
**A-105** (the guard step follows the suite step) as assertions about
`ci.yaml`'s **step shape**. Collapsing those four steps into one script call
turns all three red. A coder may not edit frozen acceptance cases; it may
amend the spec in the open and take a fresh cross-family review. That is a
real and reasonable next packet — it is not this one, and it is reported to
the product manager rather than smuggled in.

**What keeps the two from forking meanwhile** is that both call the *same*
guard file with the same arguments, and **A-207** asserts exactly that. If a
future change moves or renames the guard, both callers must move together or
that case goes red.

## S5 · Out of scope, stated so a reviewer can hold it

`service/**` source and tests — including adding `GET /api/auth/login`, the
rejected repair (Q-018; and coverage there is thin, which is `BACKLOG.md`
item 4) · `backend/**` · `.github/workflows/ci.yaml` (§S4) ·
`frontend/src/views/LoginView.vue` and the inert `gap-*` classes
(`BACKLOG.md` item 3, `#6` — the chosen repair does not open that file, so the
entry's own "ships free alongside item 1" condition is not met) ·
`frontend/e2e/**`, which drives `backend/` (`BACKLOG.md` item 4) ·
the root `package.json`'s `version` (§S3b) · `roadmap/**`, the product
manager's · **deploying (Q-012, Q-018)** · `LICENSE` (Q-021) ·
`pumasi/catalog.json` (Q-019) · `CLAUDE.md` · `web/` and `pumasi-web` ·
`HUMAN.md`.

---

## Frozen acceptance cases

Nine cases, in `frontend/src/signed-out-entry.spec.ts`. Each names the clause
it exercises, whether it was **red against the change-absent worktree**
(`2bd3ba7`), and the **single mutation** that turns it red on the final tree.
Every mutation was run; the evidence is in the implementation commit.

| # | Case | Clause | Measured against the change-absent tree | Single mutation that turns it red on the final tree — every one was run |
| :-- | :--- | :--- | :--- | :--- |
| **A-200** | the scanner A-201 uses reaches a non-trivial number of shipped frontend sources, excludes `*.spec.ts`, and flags a fixture containing the forbidden target while sparing the two live sub-routes | non-vacuity guard | **green (2 of 2) — correctly** | make the scanner's pattern match nothing → A-200 red, A-201 green, which is the pair's whole point |
| **A-201** | no shipped file under `frontend/src/`, comments stripped, constructs a navigation target at the bare `/api/auth/login` | S1b | **RED (1 of 1)** — `utils/http.ts:30` | restore `loginRedirectUrl`'s body |
| **A-202** | `SignedOutView.vue` imports `loginPageUrl` from `../utils/http`, computes its target with it, binds the button to that target, and does not name `loginRedirectUrl` | S1a | **RED (2 of 3)** — the third is green, correctly; see below | swap the import back |
| **A-203** | through this app's own router, `loginPageUrl("/")` resolves to route `login` with `meta.public`; the bare `/api/auth/login` resolves to `not-found` | S1c | **green (2 of 2) — correctly** | rename the `login` route |
| **A-204** | the root `package.json` `test` script, expanded through its own `npm run` references, still runs the frontend unit suite and `vue-tsc` with `-b` | S3a | **green — correctly** | replace `vue-tsc -b --force` with `vue-tsc --noEmit` |
| **A-205** | that same expansion invokes the service suite runner | S2a | **RED** — the string `service` does not occur in it | drop `&& npm run test:service` |
| **A-206** | the runner exists, is executable, and orders itself `npm ci` → `npm run build` → suite → guard | S2b, S2c | **RED (2 of 2)** — the file does not exist | move the guard call above the suite call |
| **A-207** | the runner and `ci.yaml`'s `service` job invoke **the same** guard path, and that file exists and is executable | S2c, S4 | **RED (1 of 2)** — the second is green, correctly; see below | point the runner at a copy of the guard |
| **A-208** | the root `package.json` has no `version` key; `ci.yaml` still defines `backend`, `frontend`, `service`, `e2e` | S3b, S3c | **green (2 of 2) — correctly** | add `"version"` to the root `package.json` |

**What "the change-absent tree" means here, precisely.** `2bd3ba7` plus two
things that are not the repair: this case file itself, and the `routes.ts`
move described in §S1. `spec/0002` measured the same way — A-104 was run
against a tree where the guard it exercises did not exist. Nothing in either
backlog item is present.

**The two sub-assertions that were green before and are not decorative.**
A-202's *"binds the button to that target"* was green at the change-absent
tree because the repair does not touch the binding — `:href="signInUrl"` is
right and stays; what changes is what `signInUrl` is computed from. It is
asserted anyway, because a later packet converting the button to a router push
would silently take the full-document navigation §S1 reason 4 argues for.
A-207's *"and that file exists and is executable"* was green because
`spec/0002` built the guard; it is asserted because this change makes a second
caller depend on it, and a guard that is deleted or loses its `+x` bit would
otherwise fail at gate time with a shell error rather than at test time with a
reason.

### The four wholly-green cases, and why none is decorative

**A-200 is the reader guard**, the analogue of `spec/0002`'s A-100. A-201 is a
whole-tree text search, and a search that silently matches no files passes
forever. A-200 asserts the scanner reached a non-trivial number of files *and*
that, handed a fixture containing the forbidden target, it reports it. Its
mutation — breaking the pattern — turns A-200 red while leaving A-201 green,
which is the pair's whole point.

**A-203 is a premise case**, the analogue of A-103. It does not describe the
repair; it describes the two facts the repair rests on — that `/login` is a
route this app has and can be reached without a session, and that the bare
`/api/auth/login` is not a route this app has, so the old target was a dead
end inside the SPA as well as at the worker. It is green before and after, and
its job is to go **red the day either stops being true**, at which point §S1's
argument must be re-read rather than silently inherited.

**A-204 and A-208 are preservation cases**, the analogue of A-005 and A-109.
Their whole value is that they were green before and must stay green: A-204
fails the packet that satisfies "make the gate cover the served tree" by making
the gate smaller, and A-208 fails the packet that takes the product manager's
item 6 on the way past. An invariant nobody asserts is an invariant somebody
deletes.

### What these cases do **not** claim

**A-201, A-202, A-204, A-205, A-206, A-207 and A-208 read files as text.** They
assert what `package.json`, `ci.yaml`, the runner script and the `.vue` SFC
*say*. They cannot assert what npm, GitHub Actions or Vue *do* with them. This
spec does not pretend otherwise, and it is the same limit `spec/0002` stated
for its own `ci.yaml` cases.

The behavioural halves are proven separately and recorded in the
implementation commit:

- **Item 1** — a real Chromium, driving a real `wrangler dev` of `service/`
  with `frontend/dist` behind its `ASSETS` binding: load `/signed-out`, click
  *Sign in again*, read the URL and the rendered body. Run **before** the
  change and **after** it. **A green `e2e` job is not offered as evidence and
  would not be evidence**: that job drives `backend/`, the one tree where the
  broken route exists.
- **Item 2** — the root `npm test` output before and after, quoting the
  service suite's own reported `# pass` / `# fail` counts and the guard's own
  summary line. Exit `0` is not the evidence; the counts are.

**A-203 is the one structural case that executes** — it builds a router from
the application's own exported `routes` and resolves paths through it.

### The defect this repository has now shipped twice, checked for a third time

`spec/0001` A-003 and `spec/0002` A-102/A-105/A-106 all had the same defect: a
case that searches a text for a string that the text also uses to *talk about*
that string. Four frozen cases across two specs were green for the wrong
reason.

**A-201 is the exact shape that defect takes.** It searches
`frontend/src/**` for a forbidden URL — and the case file that performs the
search lives under `frontend/src/` and must name that URL in order to search
for it. Three things are done about it, in the code and not only here:

1. The scan **excludes `*.spec.ts`**, so no acceptance-case file can satisfy or
   violate a case. Frozen cases are not shipped to a browser; the clause is
   about what is.
2. It **strips line and block comments** before matching, so a comment
   explaining the bug cannot be read as the bug — this is `spec/0002`
   amendment 1 applied before it was needed rather than after.
3. The forbidden literal is **assembled from fragments** in the case file, so
   it does not appear verbatim in the scanned tree even if rule 1 is later
   relaxed.

And, per the method rather than the fix: **every case above was run against
`2bd3ba7` before this spec was frozen**, and the "Red at `2bd3ba7`?" column
records what came back, not what was intended. A frozen case is not known to
be able to fail until it has been run against the tree it exists to reject.
