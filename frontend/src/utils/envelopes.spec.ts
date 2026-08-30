import { describe, expect, it } from "vitest";
import {
  actionNeeded,
  actionRequired,
  expiringSoon,
  inView,
  isTurnOf,
  lastChange,
  matchesSearch,
  normalizeSearch,
  toRow,
  waitingForMyTurn,
} from "./envelopes";
import type { SubmissionOut, SubmitterOut } from "../types";

let nextId = 1;

function submitter(overrides: Partial<SubmitterOut> = {}): SubmitterOut {
  const id = nextId++;
  return {
    id,
    user: { id: 100 + id, name: `Person ${id}`, email: `person${id}@pumasi.ai`, is_external: false },
    role: `Signer ${id}`,
    status: "pending",
    signed_at: null,
    email_status: "sent",
    last_reminded_at: null,
    reminder_count: 0,
    order_index: 0,
    is_cc: false,
    ...overrides,
  };
}

function envelope(overrides: Partial<SubmissionOut> = {}): SubmissionOut {
  const submitters = overrides.submitters ?? [submitter()];
  return {
    id: nextId++,
    public_uid: "uid",
    title: "Vendor Agreement",
    message: null,
    status: "pending",
    created_at: "2026-08-01T00:00:00Z",
    completed_at: null,
    expires_at: null,
    reminders_enabled: true,
    reminder_interval_days: 3,
    template: { id: 1, name: "Doc" } as SubmissionOut["template"],
    sender: { id: 1, name: "Sender", email: "sender@pumasi.ai", is_external: false },
    submitters,
    my_submitter_id: submitters[0]?.id ?? null,
    archived_by_me: false,
    has_certificate: false,
    ...overrides,
  };
}

describe("actionNeeded / actionRequired", () => {
  it("is true for a pending envelope where I'm an unsigned signer whose turn it is", () => {
    expect(actionNeeded(envelope())).toBe(true);
  });

  it("is false once the envelope is declined or voided, even if I never signed", () => {
    expect(actionNeeded(envelope({ status: "declined" }))).toBe(false);
    expect(actionNeeded(envelope({ status: "cancelled" }))).toBe(false);
  });

  it("is false for drafts and expired envelopes", () => {
    expect(actionNeeded(envelope({ status: "draft" }))).toBe(false);
    expect(actionNeeded(envelope({ status: "expired" }))).toBe(false);
    expect(waitingForMyTurn(envelope({ status: "expired" }))).toBe(false);
  });

  it("is false for CC recipients", () => {
    const me = submitter({ is_cc: true, role: "" });
    expect(actionNeeded(envelope({ submitters: [me, submitter()], my_submitter_id: me.id }))).toBe(false);
  });

  it("is false while an earlier order group hasn't signed (waitingForMyTurn instead)", () => {
    const first = submitter({ order_index: 0 });
    const me = submitter({ order_index: 1 });
    const env = envelope({ submitters: [first, me], my_submitter_id: me.id });
    expect(actionNeeded(env)).toBe(false);
    expect(waitingForMyTurn(env)).toBe(true);
  });

  it("becomes true once the earlier group completes", () => {
    const first = submitter({ order_index: 0, status: "completed", signed_at: "2026-08-02T00:00:00Z" });
    const me = submitter({ order_index: 1 });
    const env = envelope({ submitters: [first, me], my_submitter_id: me.id });
    expect(actionNeeded(env)).toBe(true);
    expect(waitingForMyTurn(env)).toBe(false);
  });

  it("CC rows never gate the turn", () => {
    const cc = submitter({ is_cc: true, role: "", order_index: 0 });
    const me = submitter({ order_index: 1 });
    const env = envelope({ submitters: [cc, me], my_submitter_id: me.id });
    expect(isTurnOf(env, me)).toBe(true);
  });

  it("actionRequired excludes envelopes I archived (dashboard cards)", () => {
    expect(actionRequired(envelope({ archived_by_me: true }))).toBe(false);
    expect(actionRequired(envelope())).toBe(true);
  });
});

describe("inView", () => {
  it("archived envelopes appear only in the Archived view", () => {
    const row = toRow(envelope({ archived_by_me: true }), 999);
    expect(inView(row, "archived")).toBe(true);
    expect(inView(row, "inbox")).toBe(false);
    expect(inView(row, "action")).toBe(false);
  });

  it("inbox includes any envelope where I'm a recipient (CC included)", () => {
    const me = submitter({ is_cc: true, role: "" });
    const row = toRow(envelope({ submitters: [me, submitter()], my_submitter_id: me.id }), 999);
    expect(inView(row, "inbox")).toBe(true);
    expect(inView(row, "action")).toBe(false);
  });

  it("drafts live in the Drafts view, not Sent (sender only)", () => {
    const draft = toRow(envelope({ status: "draft" }), 1); // viewer id 1 = the sender
    expect(inView(draft, "drafts")).toBe(true);
    expect(inView(draft, "sent")).toBe(false);

    const sent = toRow(envelope(), 1);
    expect(inView(sent, "sent")).toBe(true);
    expect(inView(sent, "drafts")).toBe(false);
  });

  it("action view is turn-aware", () => {
    const first = submitter({ order_index: 0 });
    const me = submitter({ order_index: 1 });
    const row = toRow(envelope({ submitters: [first, me], my_submitter_id: me.id }), 999);
    expect(inView(row, "action")).toBe(false);
    expect(row.waitingForTurn).toBe(true);
  });

  it("keeps unsent drafts out of the Inbox even when the sender is a recipient", () => {
    // viewer id 1 = the envelope's sender, and my_submitter_id defaults to
    // submitters[0].id, so the sender addressed themselves as a signer.
    const row = toRow(envelope({ status: "draft" }), 1);
    expect(inView(row, "inbox")).toBe(false);
    expect(inView(row, "drafts")).toBe(true);
  });
});

describe("search", () => {
  it("normalizeSearch survives Vuetify's clearable null (regression: dashboard crash)", () => {
    expect(normalizeSearch(null)).toBe("");
    expect(normalizeSearch(undefined)).toBe("");
    expect(normalizeSearch("  AcMe  ")).toBe("acme");
  });

  it("matches title, sender, and participants case-insensitively", () => {
    const row = toRow(envelope(), 999);
    expect(matchesSearch(row, "vendor agreement")).toBe(true);
    expect(matchesSearch(row, "sender@pumasi.ai")).toBe(true);
    expect(matchesSearch(row, row.submission.submitters[0]!.user.name.toLowerCase())).toBe(true);
    expect(matchesSearch(row, "no-such-person")).toBe(false);
  });

  it("matches the envelope ID (the watermark/certificate stamp people paste back)", () => {
    const row = toRow(envelope({ public_uid: "4F5C2E91B7A04D3E9C12AB34CD56EF78".toLowerCase() }), 999);
    expect(matchesSearch(row, "4f5c2e91b7a04d3e9c12ab34cd56ef78")).toBe(true);
    expect(matchesSearch(row, "9c12ab34")).toBe(true); // partial paste still finds it
  });
});

describe("expiringSoon", () => {
  const now = new Date("2026-08-23T00:00:00Z");

  it("is true for a pending envelope due within six days (DocuSign's window)", () => {
    expect(expiringSoon(envelope({ expires_at: "2026-08-26T00:00:00Z" }), now)).toBe(true);
  });

  it("includes an already past-due envelope the daily sweep hasn't flipped yet", () => {
    expect(expiringSoon(envelope({ expires_at: "2026-08-22T00:00:00Z" }), now)).toBe(true);
  });

  it("is false with no deadline, a distant deadline, or a non-pending status", () => {
    expect(expiringSoon(envelope(), now)).toBe(false);
    expect(expiringSoon(envelope({ expires_at: "2026-10-01T00:00:00Z" }), now)).toBe(false);
    expect(
      expiringSoon(envelope({ status: "completed", expires_at: "2026-08-24T00:00:00Z" }), now),
    ).toBe(false);
  });
});

describe("expiring / attention views", () => {
  const now = new Date("2026-08-23T00:00:00Z");

  it("expiring view shows pending envelopes due soon, for senders and recipients alike", () => {
    const row = toRow(envelope({ expires_at: "2026-08-25T00:00:00Z" }), 999);
    expect(inView(row, "expiring", now)).toBe(true);
    expect(inView(toRow(envelope(), 999), "expiring", now)).toBe(false);
  });

  it("attention view shows the sender's pending envelopes with a bounced recipient", () => {
    const bounced = submitter({ email_status: "failed" });
    const mine = toRow(envelope({ submitters: [bounced] }), 1); // viewer 1 = sender
    expect(inView(mine, "attention", now)).toBe(true);
    // Not my envelope → not my problem to fix.
    expect(inView(toRow(envelope({ submitters: [submitter({ email_status: "failed" })] }), 999), "attention", now)).toBe(false);
    // Nothing bounced → nothing to fix.
    expect(inView(toRow(envelope(), 1), "attention", now)).toBe(false);
  });

  it("archived envelopes stay out of both views", () => {
    const row = toRow(envelope({ expires_at: "2026-08-25T00:00:00Z", archived_by_me: true }), 1);
    expect(inView(row, "expiring", now)).toBe(false);
  });
});

describe("lastChange", () => {
  it("takes the latest of created/signed/reminded/completed", () => {
    const signed = submitter({ signed_at: "2026-08-05T00:00:00Z" });
    const reminded = submitter({ last_reminded_at: "2026-08-06T00:00:00Z" });
    const env = envelope({ submitters: [signed, reminded] });
    expect(lastChange(env)).toBe("2026-08-06T00:00:00Z");
  });
});
