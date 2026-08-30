import { describe, expect, it } from "vitest";
import { envelopeStatusColor, envelopeStatusLabel, signerStatusLabel } from "./labels";

describe("void language", () => {
  it('renders backend "cancelled" as "Voided" everywhere', () => {
    // A regression to "Cancelled" would previously have shipped green —
    // nothing asserted the rename.
    expect(envelopeStatusLabel("cancelled")).toBe("Voided");
    expect(envelopeStatusColor("cancelled")).toBe("grey");
  });

  it("covers every envelope status with a label", () => {
    expect(envelopeStatusLabel("pending")).toBe("In progress");
    expect(envelopeStatusLabel("completed")).toBe("Completed");
    expect(envelopeStatusLabel("declined")).toBe("Declined");
    expect(envelopeStatusLabel("draft")).toBe("Draft");
    expect(envelopeStatusLabel("expired")).toBe("Expired");
  });

  it("labels signer statuses", () => {
    expect(signerStatusLabel("completed")).toBeTruthy();
    expect(signerStatusLabel("pending")).toBeTruthy();
  });

  it('labels a draft signer "Not sent yet", not "Sent"', () => {
    expect(signerStatusLabel("pending", "draft")).toBe("Not sent yet");
    expect(signerStatusLabel("pending", "pending")).toBe("Sent");
    expect(signerStatusLabel("pending")).toBe("Sent");
  });
});
