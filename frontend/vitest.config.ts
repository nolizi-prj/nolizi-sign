import { defineConfig } from "vitest/config";

// Unit tests for pure frontend logic (src/utils). Playwright owns e2e —
// vitest deliberately only picks up *.spec.ts under src/ so the two never
// collide over the e2e/ directory.
export default defineConfig({
  test: {
    include: ["src/**/*.spec.ts"],
    environment: "node",
  },
});
