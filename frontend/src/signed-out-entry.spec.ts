/**
 * Frozen acceptance cases A-200 … A-208 for spec/0003 — "the way back in, and
 * a gate that ran the tree it is read as covering" (roadmap/BACKLOG.md items
 * 1 and 2, taken in one packet because both entries say to).
 *
 * A-200 … A-203 are item 1: a signed-out user clicked the only button on the
 * page and was handed the worker's error JSON, because the button navigated
 * to a route that exists only in backend/ — the tree no user reaches.
 *
 * A-204 … A-208 are item 2: `npm test` at this repository's root, which is
 * step 1 of pumasi/tools/gate.sh, ran 69 frontend assertions and zero on the
 * tree that answers sign.pumasi.ai.
 *
 * These cases read package.json, ci.yaml, the runner script and the SFC at
 * test time. Nothing from any of them is copied in here; a copy would fork
 * from its source (L-007).
 *
 * WHAT THESE CASES DO NOT CLAIM. Every case but A-203 reads a file as TEXT.
 * They assert what those files say, not what npm, GitHub Actions or Vue do
 * with them. The behavioural halves are proven elsewhere and recorded in the
 * implementation commit: item 1 by a real browser driving a real
 * `wrangler dev` of service/, before and after; item 2 by the root `npm test`
 * output before and after, quoting the service suite's own reported counts.
 * A green `e2e` job is not offered as evidence for item 1 and would not be
 * evidence — that job drives backend/, the one tree where the broken route
 * exists.
 *
 * THE DEFECT THIS REPOSITORY HAS SHIPPED TWICE. spec/0001 A-003 and
 * spec/0002 A-102/A-105/A-106 were each a case that searched a text for a
 * string the text also used to TALK ABOUT that string. A-201 is exactly that
 * shape — it searches frontend/src for a URL, and this file is under
 * frontend/src and has to name that URL to search for it. Three defences, in
 * the code rather than only in the spec: the scan excludes *.spec.ts, it
 * strips whole-line comments, and the forbidden literal is assembled from
 * fragments below so it never appears verbatim in the scanned tree.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it } from "vitest";

import { routes } from "./router/routes";
import { loginPageUrl } from "./utils/http";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");

const read = (rel: string) => fs.readFileSync(path.join(repoRoot, rel), "utf8");

/**
 * Whole-line `//`, `*`, `/*` and `<!--` comments removed.
 *
 * Whole lines only, deliberately — the same limit spec/0002's amendment 1
 * settled on. A `//` mid-line is legitimate inside a URL (`https://`) and
 * stripping from it would corrupt the very strings these cases search for.
 */
const stripLineComments = (text: string) =>
  text
    .split("\n")
    .filter((line) => !/^\s*(\/\/|\/\*|\*|<!--)/.test(line))
    .join("\n");

/** Whole-line `#` comments removed — for shell and YAML. */
const stripHashComments = (text: string) =>
  text
    .split("\n")
    .filter((line) => !/^\s*#/.test(line))
    .join("\n");

// ── item 1 ────────────────────────────────────────────────────────────────

/**
 * The forbidden navigation target, assembled rather than written.
 *
 * `/api/auth/login` with nothing word-like or `/` after it. The negative
 * lookahead is not decoration: `/api/auth/login/request` and
 * `/api/auth/login/verify` ARE live worker routes (service/src/durable.ts
 * :775 and :798) and must not be flagged. It is the BARE path that no tree
 * serving users answers — verified live, 404 {"error":"Endpoint not found"}.
 */
const DEAD_LOGIN_ROUTE = new RegExp(["/api", "/auth", "/login"].join("") + "(?![\\w/])");

/** Every file under frontend/src that ships to a browser. */
function shippedSources(): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (/\.(ts|vue)$/.test(entry.name) && !/\.spec\.ts$/.test(entry.name)) {
        out.push(full);
      }
    }
  };
  walk(path.join(repoRoot, "frontend", "src"));
  return out;
}

/** Files whose code (not comments) builds a navigation target at the dead route. */
function filesHittingDeadLoginRoute(files: string[]): string[] {
  return files.filter((f) =>
    DEAD_LOGIN_ROUTE.test(stripLineComments(fs.readFileSync(f, "utf8"))),
  );
}

describe("A-200 · the scanner A-201 depends on is not vacuous", () => {
  it("reaches a non-trivial number of shipped frontend sources", () => {
    const files = shippedSources();
    expect(files.length).toBeGreaterThan(20);
    // It must be reading the real tree, not an empty walk that would make
    // A-201 pass forever.
    expect(files.some((f) => f.endsWith(path.join("utils", "http.ts")))).toBe(true);
    expect(files.some((f) => f.endsWith(path.join("views", "SignedOutView.vue")))).toBe(true);
    // And it must exclude the acceptance-case files, or this very file would
    // decide the case (the spec/0001 A-003 defect).
    expect(files.some((f) => f.endsWith(".spec.ts"))).toBe(false);
  });

  it("flags a fixture that contains the forbidden target, and spares the live sub-routes", () => {
    const bad = 'const u = "' + ["/api", "/auth", "/login"].join("") + '?next=%2F";';
    const goodRequest = 'http.post("' + ["/api", "/auth", "/login", "/request"].join("") + '");';
    const goodVerify = 'http.post("' + ["/api", "/auth", "/login", "/verify"].join("") + '");';
    expect(DEAD_LOGIN_ROUTE.test(bad)).toBe(true);
    expect(DEAD_LOGIN_ROUTE.test(goodRequest)).toBe(false);
    expect(DEAD_LOGIN_ROUTE.test(goodVerify)).toBe(false);
    // And a comment about the bug is not the bug.
    expect(DEAD_LOGIN_ROUTE.test(stripLineComments("// " + bad))).toBe(false);
  });
});

describe("A-201 · no shipped frontend source navigates to the dead login route", () => {
  it("finds none (S1b)", () => {
    expect(
      filesHittingDeadLoginRoute(shippedSources()).map((f) => path.relative(repoRoot, f)),
    ).toEqual([]);
  });
});

describe("A-202 · SignedOutView sends the user to the SPA login page", () => {
  const sfc = stripLineComments(read("frontend/src/views/SignedOutView.vue"));

  it("imports loginPageUrl from utils/http and computes its sign-in target with it (S1a)", () => {
    expect(sfc).toMatch(/import\s*\{[^}]*\bloginPageUrl\b[^}]*\}\s*from\s*["']\.\.\/utils\/http["']/);
    expect(sfc).toMatch(/const\s+signInUrl\s*=\s*loginPageUrl\(/);
  });

  it("binds the button to that target", () => {
    expect(sfc).toMatch(/:href="signInUrl"/);
  });

  it("does not name loginRedirectUrl anywhere (S1a)", () => {
    expect(sfc).not.toMatch(/loginRedirectUrl/);
  });
});

describe("A-203 · the destination is a route this app has, and the old target was not", () => {
  const router = createRouter({ history: createMemoryHistory(), routes });

  it("loginPageUrl('/') resolves to the login route, reachable without a session (S1c)", () => {
    const resolved = router.resolve(loginPageUrl("/"));
    expect(resolved.name).toBe("login");
    expect(resolved.matched.length).toBeGreaterThan(0);
    expect(resolved.matched[0]?.meta?.public).toBe(true);
  });

  it("the bare /api/auth/login resolves to not-found — a dead end inside the SPA too", () => {
    const resolved = router.resolve(["/api", "/auth", "/login"].join(""));
    expect(resolved.name).toBe("not-found");
  });
});

// ── item 2 ────────────────────────────────────────────────────────────────

const ROOT_PKG = JSON.parse(read("package.json")) as {
  version?: string;
  scripts: Record<string, string>;
};

/**
 * The root `test` script with `npm run <name>` replaced by the script it
 * names, to a fixed point. What the gate runs is the expansion, not the one
 * line; splitting a script in two must not be able to hide a half.
 *
 * Only names defined in THIS package.json expand — `npm run test:unit` names
 * a script in frontend/package.json and stays literal, which is what makes
 * A-204's assertion meaningful.
 */
function expandedRootTestScript(): string {
  let text = ROOT_PKG.scripts.test ?? "";
  for (let i = 0; i < 10; i++) {
    const next = text.replace(
      /npm run ([\w:-]+)/g,
      (whole, name: string) => ROOT_PKG.scripts[name] ?? whole,
    );
    if (next === text) break;
    text = next;
  }
  return text;
}

const GUARD_RE = /[\w./-]*assert-service-suite-ran\.sh/;
const isExecutable = (rel: string) =>
  (fs.statSync(path.join(repoRoot, rel)).mode & 0o111) !== 0;

describe("A-204 · the frontend half of the gate is not shrunk to make room", () => {
  it("still runs the frontend unit suite and type-checks with -b (S3a)", () => {
    const script = expandedRootTestScript();
    expect(script).toMatch(/npm run test:unit/);
    expect(script).toMatch(/vue-tsc\b[^&|]*\s(?:-b|--build)\b/);
  });
});

describe("A-205 · the root test script runs the served tree's suite", () => {
  it("invokes the service suite runner (S2a)", () => {
    expect(expandedRootTestScript()).toMatch(/run-service-suite\.sh/);
  });
});

describe("A-206 · the runner installs, builds, runs and then proves it ran", () => {
  const rel = ".github/scripts/run-service-suite.sh";

  it("exists and is executable", () => {
    expect(fs.existsSync(path.join(repoRoot, rel))).toBe(true);
    expect(isExecutable(rel)).toBe(true);
  });

  it("orders itself: npm ci, then build, then the suite, then the guard (S2b, S2c)", () => {
    const body = stripHashComments(read(rel));
    const install = body.indexOf("npm ci");
    const build = body.indexOf("npm run build");
    const suite = body.indexOf("npm test");
    const guard = body.search(GUARD_RE);
    // Each must be present before any ordering claim is made about it —
    // indexOf returns -1 for absent, and -1 is less than every index, which
    // is the hole spec/0002 A-107 was amended to close.
    for (const [what, at] of Object.entries({ install, build, suite, guard })) {
      expect(at, `${what} not found in ${rel}`).toBeGreaterThanOrEqual(0);
    }
    expect(install).toBeLessThan(build);
    expect(build).toBeLessThan(suite);
    expect(suite).toBeLessThan(guard);
  });
});

describe("A-207 · one guard, in one place, called by both the gate and CI", () => {
  it("the runner and ci.yaml's service job name the same guard file (S2c, S4)", () => {
    const fromRunner = stripHashComments(read(".github/scripts/run-service-suite.sh")).match(GUARD_RE);
    const fromCi = stripHashComments(read(".github/workflows/ci.yaml")).match(GUARD_RE);
    expect(fromRunner, "the runner does not invoke the guard").not.toBeNull();
    expect(fromCi, "ci.yaml does not invoke the guard").not.toBeNull();
    expect(fromRunner?.[0]).toBe(fromCi?.[0]);
  });

  it("and that file exists and is executable", () => {
    const rel = ".github/scripts/assert-service-suite-ran.sh";
    expect(fs.existsSync(path.join(repoRoot, rel))).toBe(true);
    expect(isExecutable(rel)).toBe(true);
  });
});

describe("A-208 · what this packet must not take on the way past", () => {
  it("the root package.json still has no version field (S3b — PR-1 is BACKLOG item 6)", () => {
    expect(Object.prototype.hasOwnProperty.call(ROOT_PKG, "version")).toBe(false);
  });

  it("ci.yaml still defines backend, frontend, service and e2e (S3c)", () => {
    const jobs = stripHashComments(read(".github/workflows/ci.yaml"))
      .split("\n")
      .filter((line) => /^ {2}[a-z][\w-]*:\s*$/.test(line))
      .map((line) => line.trim().replace(/:$/, ""));
    expect(jobs).toEqual(expect.arrayContaining(["backend", "frontend", "service", "e2e"]));
  });
});
