import { describe, expect, it } from "vitest";
import { nextTourIndex } from "./tour";

describe("nextTourIndex", () => {
  it("advances to the next incomplete field after the current one", () => {
    expect(nextTourIndex([true, false, false], 0)).toBe(1);
  });

  it("skips completed fields", () => {
    expect(nextTourIndex([true, true, false], 0)).toBe(2);
  });

  it("wraps around to an earlier incomplete field", () => {
    // The signer skipped field 0 and is parked on the last field.
    expect(nextTourIndex([false, true, true], 2)).toBe(0);
  });

  it("returns the current field when it is the only incomplete one", () => {
    // "Field 1 of 1": Next must re-scroll to the field, not no-op.
    expect(nextTourIndex([false], 0)).toBe(0);
    expect(nextTourIndex([true, false, true], 1)).toBe(1);
  });

  it("moves to the cyclically next field when everything is complete", () => {
    expect(nextTourIndex([true, true], 0)).toBe(1);
    expect(nextTourIndex([true, true], 1)).toBe(0);
  });

  it("returns null when there are no fields", () => {
    expect(nextTourIndex([], 0)).toBeNull();
  });
});
