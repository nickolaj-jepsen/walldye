/** The specs' `test`: Playwright's, failing any test whose page throws an uncaught error. */
import { test as base, expect } from '@playwright/test';

export const test = base.extend<{ pageErrors: undefined }>({
  pageErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on('pageerror', (e) => errors.push(`${e.name}: ${e.message}`));
      await use(undefined);
      expect(errors, 'uncaught errors in the page').toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
