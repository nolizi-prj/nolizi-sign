/**
 * Frozen acceptance cases A-101 … A-109 for spec/0002 — "the gate covers the
 * tree users actually meet" (roadmap/BACKLOG.md item 2 = pumasi/DECISIONS.md
 * Q-018 parts (a) and (b)).
 *
 * These cases exist because this repository ships two complete backends for
 * one product and CI tested only the one nobody reaches: 541 `def test_`
 * functions under backend/, six Playwright specs against a Docker image of
 * that same FastAPI tree, and zero jobs touching service/ — the Cloudflare
 * Worker that answers sign.pumasi.ai.
 *
 * They read .github/workflows/ci.yaml, CLAUDE.md and service/package.json at
 * test time. Nothing from any of them is copied in here; a copy would fork
 * from its source (L-007).
 *
 * Each case names the mutation that turns it red. If you cannot describe an
 * execution that fails an assertion, the assertion is decorative (L-006) —
 * and the trap this whole spec is about is that `node --test dist/...` exits
 * 0 when nothing was compiled, so a service job that skipped its build would
 * be exactly that.
 *
 * WHAT THESE CASES DO NOT CLAIM: the ci.yaml and CLAUDE.md cases read those
 * files as TEXT. They assert what the files say, not what GitHub Actions does
 * with them; that half is proven by pushing the mutations and reading the
 * runs, recorded in the implementation commit. A-104 is the exception — it
 * executes the guard rather than matching its text.
 */
import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");

const read = (rel: string) => fs.readFileSync(path.join(repoRoot, rel), "utf8");

const CI_YAML = read(".github/workflows/ci.yaml");
const CLAUDE_MD = read("CLAUDE.md");
const SERVICE_PKG = JSON.parse(read("service/package.json")) as {
  scripts: Record<string, string>;
};

const GUARD = path.join(repoRoot, ".github/scripts/assert-service-suite-ran.sh");

/* ── a deliberately small reader for one file ─────────────────────────────
 * ci.yaml's jobs are the only two-space-indented keys under `jobs:`; a job's
 * own `services:`/`env:`/`steps:` sit at four. Steps are the six-space `- `
 * entries under `steps:`, in file order, which is execution order.
 *
 * The reader is guarded by A-100 below: a reader that silently matched
 * nothing would make every case in this file vacuously green, which is L-006
 * moved into the tool instead of the test.
 */
function jobBlocks(yaml: string): Map<string, string> {
  const marker = "\njobs:\n";
  const at = yaml.indexOf(marker);
  if (at < 0) throw new Error("ci.yaml has no top-level `jobs:` block");
  const out = new Map<string, string>();
  let current: string | null = null;
  let buf: string[] = [];
  for (const line of yaml.slice(at + marker.length).split("\n")) {
    const header = /^ {2}([A-Za-z0-9_-]+):\s*$/.exec(line);
    if (header) {
      if (current) out.set(current, buf.join("\n"));
      current = header[1];
      buf = [];
    } else if (current) {
      buf.push(line);
    }
  }
  if (current) out.set(current, buf.join("\n"));
  return out;
}

function stepsOf(job: string): string[] {
  const marker = "\n    steps:\n";
  const at = job.indexOf(marker);
  if (at < 0) return [];
  return job
    .slice(at + marker.length)
    .split(/\n(?= {6}- )/)
    .filter((chunk) => chunk.trim().length > 0);
}

const JOBS = jobBlocks(CI_YAML);
const SERVICE_JOB_STEPS = stepsOf(JOBS.get("service") ?? "");

/** A step that runs in `service/`. */
const inService = (step: string) => / {6}working-directory: service\s*$/m.test(step);

/** Index of the first step matching a predicate, or -1. */
const firstStep = (steps: string[], p: (s: string) => boolean) => steps.findIndex(p);

/** Every *.py under backend/, for A-109's "the suite is still there". */
function pythonFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === ".venv" || entry.name === "__pycache__") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) pythonFiles(full, acc);
    else if (entry.name.endsWith(".py")) acc.push(full);
  }
  return acc;
}

/** A scratch directory that the OS reclaims; never inside the repository. */
function scratch(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

describe("A-100 · the reader used by the cases below actually reads", () => {
  // Not a spec clause — a guard on the tool. Turns red when: the step or job
  // regexes stop matching ci.yaml's shape, which would otherwise make every
  // case in this file pass by finding nothing.
  it("finds the workflow's jobs, including the pre-existing three", () => {
    expect([...JOBS.keys()]).toEqual(
      expect.arrayContaining(["backend", "frontend", "e2e"]),
    );
  });

  it("splits a known job into its steps", () => {
    const frontend = stepsOf(JOBS.get("frontend") ?? "");
    expect(frontend.length).toBeGreaterThanOrEqual(4);
    // The frontend job type-checks; if the step reader works, this is found.
    expect(frontend.some((s) => s.includes("vue-tsc"))).toBe(true);
  });
});

describe("A-101 · CI runs the tree that serves sign.pumasi.ai (S1a)", () => {
  // Red at a49f594: no job under `jobs:` mentions service/ at all.
  // Mutation: drop `working-directory: service` from the suite step.
  it("has a job with a step that runs service/'s own test script", () => {
    expect(JOBS.has("service")).toBe(true);
    expect(SERVICE_JOB_STEPS.length).toBeGreaterThanOrEqual(4);
    const suite = firstStep(
      SERVICE_JOB_STEPS,
      (s) => inService(s) && /\bnpm test\b/.test(s),
    );
    expect(suite).toBeGreaterThanOrEqual(0);
  });
});

describe("A-102 · that job builds before it runs (S1b)", () => {
  // Red at a49f594: there is no job, so nothing builds before anything.
  // Mutation: move the Build step after the suite step.
  it("runs `npm run build` in service/ before the suite step", () => {
    const build = firstStep(
      SERVICE_JOB_STEPS,
      (s) => inService(s) && /npm run build/.test(s),
    );
    const suite = firstStep(
      SERVICE_JOB_STEPS,
      (s) => inService(s) && /\bnpm test\b/.test(s),
    );
    expect(build).toBeGreaterThanOrEqual(0);
    expect(suite).toBeGreaterThanOrEqual(0);
    expect(build).toBeLessThan(suite);
  });
});

describe("A-103 · the premise A-102 rests on, measured not assumed", () => {
  // CORRECTLY GREEN, before and after. This case does not describe the
  // change; it describes the trap the change defends against, and it is why
  // A-102, A-104 and A-105 exist. It goes red the day the premise moves —
  // the `test` script leaving dist/, or node failing an empty run — at which
  // point the guard's justification has to be re-read.
  // Mutation: change service/package.json's `test` script to run src/.
  it("service/'s test script runs the compiled tree", () => {
    expect(SERVICE_PKG.scripts.test).toMatch(/\bdist\//);
  });

  it("and that exact script reports 0 tests and exits 0 when nothing is built", () => {
    const empty = scratch("pumasi-sign-unbuilt-");
    const run = spawnSync("sh", ["-c", SERVICE_PKG.scripts.test], {
      cwd: empty,
      encoding: "utf8",
    });
    expect(run.status).toBe(0);
    expect(run.stdout).toMatch(/^# tests 0$/m);
  });
});

describe("A-104 · the job cannot be green having run nothing (S1c)", () => {
  // Red at a49f594: .github/scripts/assert-service-suite-ran.sh does not
  // exist. This is the one case here that EXECUTES its subject rather than
  // matching its text.
  // Mutation: make the script `exit 0` before its first check.
  const guard = (srcCount: number, distCount: number, tap: string | null) => {
    const dir = scratch("pumasi-sign-guard-");
    const src = path.join(dir, "src");
    const dist = path.join(dir, "dist");
    fs.mkdirSync(src);
    fs.mkdirSync(dist);
    for (let i = 0; i < srcCount; i++) {
      fs.writeFileSync(path.join(src, `case-${i}.test.ts`), "");
    }
    for (let i = 0; i < distCount; i++) {
      fs.writeFileSync(path.join(dist, `case-${i}.test.js`), "");
    }
    const tapFile = path.join(dir, "suite.tap");
    if (tap !== null) fs.writeFileSync(tapFile, tap);
    const run = spawnSync(GUARD, [src, dist, tapFile], { encoding: "utf8" });
    // Without this the whole of A-104 is decorative: spawnSync on a script
    // that does not exist returns status `null`, and `null !== 0`, so every
    // "fails when ..." case below passed against a49f594 — where the guard
    // had not been written yet. Measured, then closed.
    expect(run.error, "the guard did not execute").toBeUndefined();
    expect(typeof run.status, "the guard did not exit normally").toBe("number");
    return run.status as number;
  };

  const GREEN_TAP = "ok 1 - a\nok 2 - b\n1..2\n# tests 2\n# pass 2\n# fail 0\n";

  it("passes a suite that really ran", () => {
    expect(guard(2, 2, GREEN_TAP)).toBe(0);
  });

  it("fails an unbuilt tree — the L-006 trap this job exists to avoid", () => {
    expect(guard(2, 0, "")).toBe(1);
  });

  it("fails a partially compiled tree", () => {
    expect(guard(2, 1, GREEN_TAP)).toBe(1);
  });

  it("fails a run that reported zero passing tests", () => {
    expect(guard(2, 2, "1..0\n# tests 0\n# pass 0\n# fail 0\n")).toBe(1);
  });

  it("fails a run that reported a failing test", () => {
    expect(guard(2, 2, "# tests 2\n# pass 1\n# fail 1\n")).toBe(1);
  });

  it("fails when the suite produced no summary at all", () => {
    expect(guard(2, 2, "some npm noise and nothing else\n")).toBe(1);
  });

  it("fails when there are no test sources to run", () => {
    expect(guard(0, 0, GREEN_TAP)).toBe(1);
  });
});

describe("A-105 · the job invokes that guard, after the suite (S1c)", () => {
  // Red at a49f594: no job. A-104 proves the guard works; this proves it is
  // wired in. A guard that exists and is never called is decorative.
  // Mutation: delete the guard step from the job.
  it("calls assert-service-suite-ran.sh after running the suite", () => {
    const suite = firstStep(
      SERVICE_JOB_STEPS,
      (s) => inService(s) && /\bnpm test\b/.test(s),
    );
    const assertion = firstStep(SERVICE_JOB_STEPS, (s) =>
      s.includes("assert-service-suite-ran.sh"),
    );
    expect(assertion).toBeGreaterThanOrEqual(0);
    expect(assertion).toBeGreaterThan(suite);
  });

  it("and that script is present and executable", () => {
    expect(fs.existsSync(GUARD)).toBe(true);
    // eslint-disable-next-line no-bitwise
    expect(fs.statSync(GUARD).mode & 0o111).toBeGreaterThan(0);
  });
});

describe("A-106 · ci.yaml's type-check is able to fail (S2a)", () => {
  // Red at a49f594: ci.yaml:79 is `npx vue-tsc --noEmit`. Measured this tick
  // with a deliberate type error in frontend/src/stage.ts: `--noEmit` exits
  // 0, `-b` exits 2 — frontend/tsconfig.json is a solution file, so without
  // -b there is no program to check.
  // Mutation: restore `npx vue-tsc --noEmit`.
  it("never invokes vue-tsc without -b", () => {
    const lines = CI_YAML.split("\n").filter((l) => l.includes("vue-tsc"));
    expect(lines.length).toBeGreaterThan(0);
    for (const line of lines) expect(line).toMatch(/\s-b\b/);
  });
});

describe("A-107 · CLAUDE.md names the tree that serves users (S3a, S3b)", () => {
  // Red at a49f594: none of sign.pumasi.ai, service/, Cloudflare Worker or
  // wrangler appears in the file, which opens "FastAPI backend … hosted on
  // Railway" and whose Deployment section is entirely `railway up`.
  // Mutation: move the Railway paragraph above the worker one.
  it("names the worker, its domain and its deploy command", () => {
    expect(CLAUDE_MD).toContain("sign.pumasi.ai");
    expect(CLAUDE_MD).toContain("service/");
    expect(CLAUDE_MD).toMatch(/Cloudflare Worker/);
    expect(CLAUDE_MD).toContain("wrangler");
  });

  it("leads with the deployed tree, not the undeployed one", () => {
    // Every index is asserted present first. indexOf returns -1 for an absent
    // string and -1 is less than everything, so the ordering assertions alone
    // passed against a49f594 — a file naming neither the worker nor its
    // domain. Measured, then closed.
    const at = (needle: string) => {
      const i = CLAUDE_MD.indexOf(needle);
      expect(i, `CLAUDE.md does not mention ${needle}`).toBeGreaterThanOrEqual(0);
      return i;
    };
    expect(at("sign.pumasi.ai")).toBeLessThan(at("Railway"));
    expect(at("wrangler")).toBeLessThan(at("railway up"));
  });

  it("records that which tree is the product is still open (Q-018)", () => {
    expect(CLAUDE_MD).toContain("Q-018");
  });
});

describe("A-108 · CLAUDE.md documents a type-check that can fail (S3c)", () => {
  // Red at a49f594: CLAUDE.md:20 is `npx vue-tsc --noEmit    # type-check`.
  // Mutation: restore it.
  it("does not document `vue-tsc --noEmit`", () => {
    expect(CLAUDE_MD).not.toContain("vue-tsc --noEmit");
  });
});

describe("A-109 · nothing is bought by deletion (S4)", () => {
  // CORRECTLY GREEN, before and after — a preservation invariant, the
  // analogue of spec/0001's A-005. Its value is that it fails the packet that
  // satisfies "make the gate cover the tree users meet" by making the gate
  // smaller. Q-018's other half — retiring backend/, re-pointing the domain —
  // is the steward's.
  // Mutation: delete the e2e job.
  it("keeps the three jobs that were already there", () => {
    for (const job of ["backend", "frontend", "e2e"]) {
      expect(JOBS.has(job)).toBe(true);
    }
  });

  it("keeps both service/ test files", () => {
    for (const file of ["stamping.test.ts", "e2e-workflow.test.ts"]) {
      expect(fs.existsSync(path.join(repoRoot, "service/src/test", file))).toBe(true);
    }
  });

  it("keeps the backend suite", () => {
    const count = pythonFiles(path.join(repoRoot, "backend"))
      .map((f) => (fs.readFileSync(f, "utf8").match(/^\s*def test_/gm) ?? []).length)
      .reduce((a, b) => a + b, 0);
    expect(count).toBeGreaterThan(0);
  });
});
