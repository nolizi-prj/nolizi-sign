import { describe, expect, it } from "vitest";
import { MAX_SOURCE_FILE_BYTES, validateSourceFiles } from "./uploads";

const file = (name: string, size: number) => ({ name, size } as File);

describe("upload memory preflight", () => {
  it("accepts a normal document set", () => {
    expect(validateSourceFiles([file("offer.pdf", 2_000_000), file("benefits.pdf", 3_000_000)])).toBeNull();
  });

  it("rejects unsupported formats after selection instead of relying on the native chooser", () => {
    expect(validateSourceFiles([file("installer.exe", 1000)])).toContain("not a supported document format");
  });

  it("rejects one oversized source before reading it", () => {
    expect(validateSourceFiles([file("scan.pdf", MAX_SOURCE_FILE_BYTES + 1)])).toContain("scan.pdf");
  });

  it("rejects a set whose combined source bytes exceed the limit", () => {
    expect(validateSourceFiles([file("one.pdf", 11_000_000), file("two.pdf", 10_000_000)])).toContain("total more than 20 MB");
  });
});
