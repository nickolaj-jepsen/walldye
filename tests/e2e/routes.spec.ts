import { publishedPieces } from './helpers';
import { expect, test } from './test';

// Each kind of page once, so a DOM hook one of them lacks fails here even when no other spec opens it.
const ROUTES = ['/', `/${publishedPieces()[0].slug}`, '/about', '/no-such-piece'];

for (const route of ROUTES) {
  test(`${route} loads without page errors`, async ({ page }) => {
    await page.goto(route);
    await expect(page.locator('main')).toBeVisible();
    await page.waitForLoadState('networkidle');
  });
}
