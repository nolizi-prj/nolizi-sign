# SPEC · 0002 — the gate covers the tree users actually meet

**Intent:** [`INTENT.md`](INTENT.md) · **Backlog:** item 2 = `pumasi/DECISIONS.md`
**Q-018** parts (a) and (b)
**Frozen:** at spec review, before implementation.

The rules this change is measured against are not restated here (L-007):
`pumasi/governance/CHARTER.md` (Part 0, Part 3), `pumasi/DECISIONS.md`
**Q-012**, **Q-017**, **Q-018**, **Q-021**, `pumasi/PRODUCT-RULES.md` (v1.0,
readable only on branch `worktree-product-rules` `0115758` — that is Q-017,
and absence from `main` is not compliance), `pumasi/lessons/L-006` and
`L-007`. The facts it is measured against are `.github/workflows/ci.yaml`,
`CLAUDE.md` and `service/package.json`, read at test time rather than copied.

**Case numbering.** `spec/0001` owns **A-001 – A-006** and they keep running.
This spec numbers from **A-101** so the two sets can never collide. A-005
(spec/0001) is this change's guard on the Apache-2.0 strings and is not
duplicated here.

---

## S1 · CI runs the tree that serves `sign.pumasi.ai`

**S1a.** `.github/workflows/ci.yaml` defines a job that runs `service/`'s own
test suite — a step whose working directory is `service` and whose command is
that package's `test` script.

**S1b.** That job **builds before it runs**. `service/package.json`'s `test`
script is `node --test dist/test/*.test.js`: it executes the compiled tree,
and `service/dist/` is `.gitignore`d, so a checkout has none.

**S1c.** That job **cannot be green having run nothing.** After the suite
reports, the job asserts that the number of compiled test files equals the
number of test sources under `service/src/test/`, that the suite reported a
`# fail` count of zero, and that it reported a `# pass` count no smaller than
the number of test source files.

### Why S1c is a separate assertion and not a comment on S1b

S1b alone is not enough, and the difference is the whole lesson. A build step
can be deleted, moved, or silently stop emitting the tests (a `tsconfig.json`
`exclude`, an `outDir` change) while the job stays green, because
`node --test` **exits 0 on an unmatched glob**. Measured on a clean
`git archive` of `a49f594` with `dist/` removed: `# tests 0`, exit `0`.

So the guard in S1c is written to be **independent of S1b**: it reads the
suite's own reported counts and the compiled tree, not the workflow's step
list. Delete the build step and the job still goes red — at the guard, with
the reason printed. That independence is what A-104 exercises.

### Where the guard lives, and why that is one file and not two

The guard is a committed script, `.github/scripts/assert-service-suite-ran.sh`,
invoked by the job. It is not inlined in `ci.yaml`, for one reason: a guard
that exists only inside a workflow can only ever be *string-matched* by an
acceptance case, and a case that matches the string of its own guard proves
nothing about whether the guard works. As a script it is **executed** by
A-104 against fixtures, with no `npm install` and no network. One copy, one
place, exercised — rather than a copy in `ci.yaml` and a restatement of it in
a test (L-007).

This is a stated exception to §S5's "`ci.yaml` only", in the same shape as
`spec/0001` §S5's root `package.json` gate adapter: it is the new job's own
plumbing, not a feature, and it is named here so a reviewer can hold it.

## S2 · `ci.yaml`'s frontend type-check is able to fail

**S2a.** No `run:` in `.github/workflows/ci.yaml` invokes `vue-tsc` without
`-b`.

Measured against `a49f594`, with `const __probe: number = "s"` appended to
`frontend/src/stage.ts`:

| Command | Exit |
| :--- | :--- |
| `npx vue-tsc --noEmit` (`ci.yaml:79`, `CLAUDE.md:20`) | **0** |
| `npx vue-tsc -b` (the Build step's first half) | **2** |
| `npx vue-tsc -b --force` (the root gate adapter, `a49f594`) | **2** |

`frontend/tsconfig.json` is a solution file — empty `files`, two
`references` — so without `-b` there is no program to check. This
re-measurement **agrees with job `0026`'s**; nothing is reported as
disagreeing. CI was never blind: the Build step beside the decorative one
catches type errors today, which is why this is tidy-up inside an item that
names it, and not a defect report of its own.

## S3 · `CLAUDE.md` names the tree that serves users

**S3a.** `CLAUDE.md` names all four of: `sign.pumasi.ai`, `service/`,
Cloudflare Worker, and `wrangler`.

**S3b.** It leads with the deployed tree. The first mention of
`sign.pumasi.ai` precedes the first mention of `Railway`, and the first
mention of `wrangler` precedes the first mention of `railway up`. A reader
who stops after the opening paragraph must not come away believing the
product is deployed on Railway.

**S3c.** It does not document a type-check that cannot fail: the string
`vue-tsc --noEmit` does not appear in the file.

**S3d.** It records that which tree *is* the product is open (Q-018) and that
the `backend`/`e2e` jobs are not evidence about production — Q-018's default
part (c), carried as a sentence rather than by deleting a job.

## S4 · Nothing is bought by deletion

**S4a.** `ci.yaml` still defines the jobs `backend`, `frontend` and `e2e`.

**S4b.** `service/src/test/` still holds `stamping.test.ts` and
`e2e-workflow.test.ts`.

**S4c.** `backend/` still holds test functions.

Q-018 (a) and (b) add coverage and documentation. Retiring `backend/`,
re-pointing the domain and migrating data are the rest of that entry and are
the steward's. A packet that closed the gap by narrowing the gate would have
satisfied the headline and inverted the intent, so the invariant is asserted
rather than promised.

## S5 · Out of scope, stated so a reviewer can hold it

`service/**` source and tests (Q-018's other half; and coverage there is thin
— a finding, not a licence) · `backend/**` · `frontend/src/views/**` and the
Apache-2.0 strings (Q-021, guarded by spec/0001 A-005) · `roadmap/**`, which
is the product manager's and still ranks item 1 as pending in full ·
deploying (Q-012) · `pumasi/catalog.json` (Q-019) · `web/` and `pumasi-web` ·
`HUMAN.md` · PR-1's version number (backlog item 6).

**And one thing inside the headline that is deliberately left open.**
`pumasi/tools/gate.sh` step 1 runs `npm test` at this repository's root, and
the root `package.json` runs the frontend suite only. After this change **CI**
covers `service/` and the **merge gate** still does not. `BACKLOG.md` item 2
and Q-018 (b) both say *CI gains a job* in those words, and the root
`package.json` was authored one commit earlier under `spec/0001` §S5. Widening
it is reported to the product manager (and touches `pumasi-booking`'s Q-025
question about what `GATE: PASS` evidences) rather than taken here.

---

## Frozen acceptance cases

Nine cases. Each names the clause it exercises, whether it was **red against
the change-absent worktree** (`a49f594`), and the **single mutation** that
turns it red on the final tree. Every one of those mutations was run (L-006);
the evidence is in the implementation commit.

| # | Case | Clause | Red at `a49f594`? | Single mutation that turns it red on the final tree |
| :-- | :--- | :--- | :--- | :--- |
| **A-101** | `ci.yaml` has a job with a step whose working directory is `service` and whose command runs that package's `test` script | S1a | **RED** — no job under `jobs:` mentions `service/` at all | drop `working-directory: service` from that step |
| **A-102** | in that same job, a `service` build step precedes the suite step | S1b | **RED** (with A-101: there is no job, so no build precedes anything) | move the Build step after the suite step |
| **A-103** | `service/package.json`'s `test` script names `dist/`, and running that exact script string in an empty directory exits **0** having reported **0** tests | S1b's premise | **green — correctly** | change the `test` script to run `src/` directly |
| **A-104** | `.github/scripts/assert-service-suite-ran.sh` fails an unbuilt tree, a zero-pass run and a non-zero-fail run, and passes a real one | S1c | **RED** — the script does not exist | make the script `exit 0` before its first check |
| **A-105** | the `service` job invokes that script, after the suite step | S1c | **RED** — no job | delete the guard step from the job |
| **A-106** | no `run:` in `ci.yaml` invokes `vue-tsc` without `-b` | S2a | **RED** — `ci.yaml:79` is `npx vue-tsc --noEmit` | restore `npx vue-tsc --noEmit` |
| **A-107** | `CLAUDE.md` names `sign.pumasi.ai`, `service/`, Cloudflare Worker and `wrangler`, and names the deployed tree before the Railway one | S3a, S3b | **RED** — none of the four strings is in the file | move the Railway paragraph above the worker one |
| **A-108** | `CLAUDE.md` does not contain `vue-tsc --noEmit` | S3c | **RED** — `CLAUDE.md:20` | restore it |
| **A-109** | `ci.yaml` still defines `backend`, `frontend` and `e2e`; `service/src/test/` still holds both test files; `backend/` still holds test functions | S4a–c | **green — correctly** | delete the `e2e` job |

### The two correctly-green cases, and why each is not decorative

**A-103 is a premise case.** It does not describe this change; it describes
the trap the change defends against, and it is the reason A-102, A-104 and
A-105 exist. It is green before and after because `node --test` exits 0 on an
unmatched glob today. Its job is to go **red the day that stops being true** —
if `service/package.json`'s `test` script moves off `dist/`, or node starts
failing an empty run — at which point the guard's justification has changed
and must be re-read. A prose claim would have gone stale silently; this one
cannot. It is also what makes the L-006 argument in §S1 executable rather
than asserted.

**A-109 is a preservation case**, the analogue of `spec/0001`'s A-005. Its
whole value is that it was green before and must stay green: it fails the
packet that satisfies "make the gate cover the tree users actually meet" by
making the gate smaller. It is the assertion form of "do not delete a test, a
job, or a directory".

### What these cases do **not** claim

A-101, A-102, A-105, A-106, A-107, A-108 and A-109 read `ci.yaml` and
`CLAUDE.md` **as text**, splitting the workflow on its own job headers. They
assert what those files *say*. They cannot assert what GitHub Actions *does*
with them, and this spec does not pretend otherwise: that half is proven by
**running CI**, on scratch branches, with the mutations above actually pushed,
and the run URLs recorded in the implementation commit. A-104 is the one
structural case that is behavioural — it executes the guard.

Because the text-reading cases depend on a small reader, the reader is itself
guarded (**A-100**): the cases assert that it found the pre-existing jobs and
split a known job into a non-trivial number of steps, one of which runs
`vue-tsc`. A reader that silently matched nothing would otherwise make every
case above vacuously green, which is L-006 in the tool rather than in the
test.

### Two cases could not fail, and were caught by running them

`0026` found a frozen case that could not fail *in a case written to enforce
L-006*. This spec assumed the same and looked. **Two of these nine had that
defect**, both found by running the file against `a49f594` before freezing it
and reading which cases were green rather than trusting that they would be
red:

- **A-104**, six of its seven assertions. `spawnSync` on a script that does
  not exist returns `status: null`, and `expect(null).not.toBe(0)` passes. So
  every *"fails when …"* case was green against a tree where
  `assert-service-suite-ran.sh` had not been written — the case for the
  L-006 guard was itself L-006. Closed by asserting that the guard **executed**
  (`error` undefined, `status` a number) and by pinning the exit code to
  exactly `1` rather than "not 0".
- **A-107**'s ordering assertion. `String.indexOf` returns `-1` for an absent
  string and `-1` is less than every index, so *"the first mention of
  `sign.pumasi.ai` precedes the first mention of `Railway`"* was green against
  a `CLAUDE.md` that mentions neither the worker nor its domain. Closed by
  asserting each index is `>= 0` before comparing.

Recorded here rather than quietly fixed, because the fix is not the
interesting part: the method is. A frozen case is not known to be able to fail
until it has been run against the tree it exists to reject.

### Measured against `a49f594`, before implementation

| Case | Result | |
| :-- | :--- | :--- |
| A-100 | green | correctly — a guard on the reader, which works on the existing file |
| A-101 | **red** | |
| A-102 | **red** | |
| A-103 | green | correctly — a premise case; see above |
| A-104 | **red** (7 of 7) | green in 6 of 7 before the hole above was closed |
| A-105 | **red** | |
| A-106 | **red** | |
| A-107 | **red** (3 of 3) | green in 1 of 3 before the hole above was closed |
| A-108 | **red** | |
| A-109 | green | correctly — a preservation invariant; see above |

---

## Amendment log

One amendment, taken **in the open and in the right order**: amended, given a
fresh cross-family spec review, and only then built against. The first code
review OBJECTED on both `0023` and `0026` today citing CHARTER Part 3
requirement 2 — an amendment folded into the implementation commit instead —
so the ordering here is deliberate, and the amendment sits in its own commit
with no implementation in it.

| # | What | When | Spec review |
| :-- | :--- | :--- | :--- |
| 1 | **A-102, A-105 and A-106 read the workflow's comments as if they were its configuration.** The cases now strip whole-line `#` comments before matching. | before implementation was committed | see the `Reviewed-By:` trailer on the amendment commit |

**Why it was needed, and how it was found.** The `service` job's comments
explain *why* the build step must precede `npm test` — so they contain the
string `npm test`. Step chunks carry their trailing comments, so the
`npm ci` step was read as the suite step and A-102 compared the wrong pair.
A-106 had the same defect from the other direction: a comment quoting
`vue-tsc --noEmit` **in order to say that it is broken** made the case red on
a file that no longer runs it.

That is precisely `spec/0001` A-003's shape, where `MARKET.md` quoted a false
price in order to refute it and a whole-file search reported the wrong table
as backed. **The same defect has now appeared in two consecutive specs in
this repository**: a case that searches a text for a string it also uses to
*talk about* that string. It is recorded here as a pattern rather than as an
incident.

Found the same way, too: by running the frozen cases against the tree and
reading which ones were green, rather than assuming the reds would land where
intended. A case that can be flipped by a sentence nobody executes is not
measuring the file.

**Direction of the amendment.** It makes three cases *more* able to fail and
none of them easier to pass — comments can no longer satisfy an assertion,
and A-100 gains a guard that goes red if the stripping stops working. That is
the direction that cannot lower a frozen bar. Whole lines only: `#` inside a
shell `run:` block is a legitimate character and is deliberately left alone;
a trailing comment on a `run:` line could still be read as configuration, and
that limit is stated rather than papered over.
