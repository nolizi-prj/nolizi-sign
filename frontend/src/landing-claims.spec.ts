/**
 * Frozen acceptance cases A-001 … A-005 for spec/0001 — "landing page: stage
 * from the register, prices from MARKET.md" (roadmap/BACKLOG.md item 1,
 * halves (a) and (c)).
 *
 * These cases exist because a public page claimed a stage the product does
 * not have and prices the repository could not back. They read the two
 * registers — roadmap/STAGE.md and roadmap/MARKET.md — at test time and
 * compare the page against them. Nothing from either file is copied in here;
 * a copy would fork from its source exactly the way the defect being closed
 * did (L-007).
 *
 * Each case names the mutation that turns it red. If you cannot describe an
 * execution that fails an assertion, the assertion is decorative (L-006).
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { STAGE, STAGE_BADGE, STAGE_LABEL } from "./stage";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "..", "..");

const read = (rel: string) => fs.readFileSync(path.join(repoRoot, rel), "utf8");

const STAGE_MD = read("roadmap/STAGE.md");
const MARKET_MD = read("roadmap/MARKET.md");

/**
 * MARKET.md's pricing table rows — the cells read off each vendor's own page.
 *
 * A figure must be backed by one of THESE, not by the file at large. §1's
 * "A correction this file forces" paragraph quotes the landing page's own
 * false figures in order to refute them, so `$25` and `$65` are in the file
 * as prose. Searching the whole file reports the wrong table as fully backed:
 * the first draft of A-003 did exactly that and stayed green against d797c81.
 */
const MARKET_PRICE_ROWS = MARKET_MD.split("\n")
  .filter((line) => line.trim().startsWith("|"))
  .join("\n");
const STAGE_TS = read("frontend/src/stage.ts");
const LANDING_VUE = read("frontend/src/views/LandingView.vue");

/** Every rung of the ladder roadmap/STAGE.md and the role file use. */
const STAGE_WORDS = /\b(alpha|beta|launched)\b/gi;

/** All `$`-denominated figures in a blob, e.g. "$11", "$1,200", "$0". */
function moneyIn(text: string): string[] {
  return [...text.matchAll(/\$\s?\d[\d,]*(?:\.\d{1,2})?/g)].map((m) => m[0].replace(/\s/g, ""));
}

/**
 * The plan names roadmap/MARKET.md §1 tabulates, per vendor — the first cell
 * of each row of that vendor's pricing table. Parsed, never listed here, so
 * this test cannot fall behind the file it is checking.
 */
function plansByVendor(): Record<string, string[]> {
  const sections = MARKET_MD.split(/^### /m).slice(1);
  const out: Record<string, string[]> = {};
  for (const section of sections) {
    const heading = section.split("\n", 1)[0].trim();
    const plans: string[] = [];
    for (const line of section.split("\n")) {
      const cells = line.split("|").map((c) => c.trim());
      // A markdown body row: leading and trailing empty cells around >= 3 cells.
      if (cells.length < 5 || cells[0] !== "" || cells[1] === "" || /^[:\- ]+$/.test(cells[1])) continue;
      if (cells[1] === "Plan") continue;
      plans.push(cells[1]);
    }
    if (plans.length) out[heading] = plans;
  }
  return out;
}

/** The comparison table's body rows, as arrays of cell text (col 0 = capability). */
function comparisonRows(): string[][] {
  const tbody = LANDING_VUE.match(/<tbody>([\s\S]*?)<\/tbody>/);
  expect(tbody, "LandingView.vue must still have a comparison <tbody>").not.toBeNull();
  return [...tbody![1].matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map((tr) =>
    [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((td) =>
      td[1].replace(/\s+/g, " ").replace(/&amp;/g, "&").trim(),
    ),
  );
}

describe("A-001 · the stage the page carries is the stage the register records", () => {
  it("STAGE equals roadmap/STAGE.md's `Current stage:` line", () => {
    // Red when the constant and the register move apart in either direction —
    // which is the whole defect: a BETA chip against an `alpha` register.
    const m = STAGE_MD.match(/\*\*Current stage:\*\*\s*`([a-z]+)`/);
    expect(m, "roadmap/STAGE.md must state **Current stage:** `<stage>`").not.toBeNull();
    expect(STAGE).toBe(m![1]);
  });
});

describe("A-002 · a stage word is written in exactly one place", () => {
  it("LandingView.vue writes no stage word at all", () => {
    // Red the moment anyone hand-writes "Beta"/"Alpha" into the view again —
    // including in a comment, which is where the third shipped copy lived.
    expect(LANDING_VUE.match(STAGE_WORDS) ?? []).toEqual([]);
  });

  it("stage.ts writes exactly one, and it is the STAGE assignment", () => {
    // Red if the badge or the prose label is hard-coded rather than derived:
    // a hard-coded `STAGE_BADGE = "ALPHA — ACTIVE DEVELOPMENT"` is a second
    // occurrence, and the point of this module is that there is only one.
    const found = STAGE_TS.match(STAGE_WORDS) ?? [];
    expect(found).toHaveLength(1);
    expect(STAGE_TS).toMatch(new RegExp(`STAGE\\s*=\\s*"${found[0]}"`));
  });

  it("derives every user-facing form from that one constant", () => {
    expect(STAGE_LABEL.toLowerCase()).toBe(STAGE);
    expect(STAGE_BADGE.startsWith(STAGE.toUpperCase())).toBe(true);
    // STAGE_PLAYBOOK.md's Stage-1 Surface B deliverable: a prominent
    // `[ALPHA - ACTIVE DEVELOPMENT]` badge. Followed in substance, and it
    // follows the register to the next rung on its own.
    expect(STAGE_BADGE).toContain("ACTIVE DEVELOPMENT");
  });
});

describe("A-003 · no money figure on the page that MARKET.md does not carry", () => {
  it("every $ figure in LandingView.vue appears in a MARKET.md pricing table row", () => {
    // Red on the shipped "$25 – $65 / user / mo": neither figure was read off
    // DocuSign's own pricing page on 2026-08-31, so neither is in a table row.
    const unbacked = moneyIn(LANDING_VUE).filter((amount) => !MARKET_PRICE_ROWS.includes(amount));
    expect(unbacked, `figures in no roadmap/MARKET.md price row: ${unbacked.join(", ")}`).toEqual([]);
  });

  it("is capable of failing — the figures it replaced are in no price row", () => {
    // Guards the guard (L-006). If MARKET.md is ever restructured so that its
    // prose and its tables stop being distinguishable, this goes red and says
    // so, instead of A-003 quietly becoming decorative again.
    expect(MARKET_MD).toContain("$25");
    expect(MARKET_PRICE_ROWS).not.toContain("$25");
  });
});

describe("A-004 · every priced competitor cell names a plan and states that vendor's own meter", () => {
  const DOCUSIGN_COL = 2;
  const SIGNWELL_COL = 3;

  it("names a plan MARKET.md tabulates for that vendor", () => {
    // MARKET.md §1, "What this establishes ... and what it does not":
    //   "Nothing here should be restated as 'DocuSign costs X' without the
    //    plan name attached."
    // Red on the shipped cells, which carried a bare range and no plan.
    const plans = plansByVendor();
    const docusign = plans["DocuSign eSignature"] ?? [];
    const signwell = plans["SignWell"] ?? [];
    expect(docusign.length, "MARKET.md must tabulate DocuSign plans").toBeGreaterThan(0);
    expect(signwell.length, "MARKET.md must tabulate SignWell plans").toBeGreaterThan(0);

    for (const row of comparisonRows()) {
      for (const [col, vendorPlans] of [
        [DOCUSIGN_COL, docusign],
        [SIGNWELL_COL, signwell],
      ] as const) {
        const cell = row[col] ?? "";
        if (!cell.includes("$")) continue;
        const named = vendorPlans.some((plan) => cell.includes(plan));
        expect(named, `priced cell states no MARKET.md plan name: "${cell}"`).toBe(true);
      }
    }
  });

  it("prices DocuSign per user and SignWell per sender", () => {
    // MARKET.md §1: "both vendors sell per-sender subscriptions; DocuSign's
    // two mainstream business plans state a 100 envelopes per user per year
    // limit at $30 and $45 per user per month; SignWell's paid tiers state
    // unlimited documents and meter **senders** rather than documents."
    // The shipped SignWell cell said "/ user / mo". That is the factual
    // error, so it is asserted rather than derived.
    for (const row of comparisonRows()) {
      const docusign = row[DOCUSIGN_COL] ?? "";
      const signwell = row[SIGNWELL_COL] ?? "";
      if (docusign.includes("$")) {
        expect(docusign, `DocuSign priced cell must meter users: "${docusign}"`).toMatch(/\buser\b/i);
      }
      if (signwell.includes("$")) {
        expect(signwell, `SignWell priced cell must meter senders: "${signwell}"`).toMatch(/\bsender/i);
        expect(signwell, `SignWell does not meter users: "${signwell}"`).not.toMatch(/\/\s*user\b/i);
      }
    }
  });

  it("cites the source and the date the figures were read", () => {
    // MARKET.md's own rule: "Every claim about a competitor is cited or
    // absent. No exceptions, ever." The date is part of the claim.
    const date = MARKET_MD.match(/fetched\s+(\d{4}-\d{2}-\d{2})/)?.[1];
    expect(date, "MARKET.md must record the date it read the vendors' pages").toBeTruthy();
    expect(LANDING_VUE).toContain(date!);
    expect(LANDING_VUE).toContain("MARKET.md");
  });
});

describe("A-005 · this packet did not touch the Apache-2.0 claim (Q-021)", () => {
  // A scope guard, not a position. The claim is untrue today — there is no
  // LICENSE file and `gh repo view --json licenseInfo` returns null — and it
  // is pumasi/DECISIONS.md Q-021, which is the steward's both ways.
  //
  // RETIRE THIS CASE WITH Q-021. Whichever way that entry lands (the LICENSE
  // file, or the claim's removal), the answer changes these strings, and this
  // case must be updated or deleted in the same commit. It pins what this
  // packet did, not what the steward may decide.
  const shippedAt10a523d = [
    "certificates under Apache-2.0.",
    "100% Apache-2.0",
    "Apache-2.0 (Open Source)",
  ];

  for (const claim of shippedAt10a523d) {
    it(`leaves "${claim}" byte-identical to 10a523d`, () => {
      expect(LANDING_VUE).toContain(claim);
    });
  }
});
