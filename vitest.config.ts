import { defineConfig } from 'vitest/config';

// Unit tests are `*.test.ts`; Playwright owns `tests/e2e/**/*.spec.ts`.
export default defineConfig({
  test: {
    include: ['src/**/*.test.ts', 'scripts/**/*.test.ts', 'tests/unit/**/*.test.ts'],
  },
});
