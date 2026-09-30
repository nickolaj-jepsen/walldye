import { defineConfig } from 'vitest/config';

// Playwright owns `tests/e2e/**/*.spec.ts`. `parity` compares the TS ports with the Python renders
// and fixtures that `walldye build` and scripts/fixtures/regen.py write; `unit` needs neither.
export default defineConfig({
  test: {
    projects: [
      { test: { name: 'unit', include: ['tests/unit/**/*.test.ts'] } },
      { test: { name: 'parity', include: ['tests/parity/**/*.test.ts'] } },
    ],
  },
});
