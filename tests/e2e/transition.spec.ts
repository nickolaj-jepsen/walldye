import { expect, type Page, test } from '@playwright/test';

/**
 * The plate carried between a grid and its page as a cross-document view transition. Each page
 * records how its pagereveal went in `__vt`: "none" without a transition, "skipped", or the
 * view-transition-name of the plate it landed on.
 */
test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 900 } });

test.beforeEach(async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium', 'cross-document view transitions are Chromium-only here');
  await page.addInitScript(() => {
    const w = window as unknown as { __vt?: string };
    addEventListener('pagereveal', (e) => {
      const vt = e.viewTransition;
      w.__vt = vt ? 'pending' : 'none';
      vt?.ready
        .then(() => {
          const named = [...document.querySelectorAll<HTMLElement>('.plate')].find(
            (p) => getComputedStyle(p).viewTransitionName === 'plate',
          );
          w.__vt = named?.dataset.plate ?? 'unnamed';
        })
        .catch(() => {
          w.__vt = 'skipped';
        });
    });
  });
});

const revealed = async (page: Page): Promise<string> => {
  await page.waitForFunction(() => {
    const v = (window as unknown as { __vt?: string }).__vt;
    return v !== undefined && v !== 'pending';
  });
  return page.evaluate(() => (window as unknown as { __vt: string }).__vt);
};

const firstSlug = (page: Page) =>
  page.locator('.grid > li').first().getAttribute('data-slug') as Promise<string>;

test('a plate carries to its page and back to the index', async ({ page }) => {
  await page.goto('/');
  const slug = await firstSlug(page);
  await page.locator(`.grid > li[data-slug="${slug}"] figure`).click();
  await page.waitForURL(`**/${slug}`);
  expect(await revealed(page)).toBe(slug);
  // The name is only held for the transition, so the next one can name another plate.
  await expect
    .poll(() =>
      page.locator('.spread .plate').evaluate((p) => getComputedStyle(p).viewTransitionName),
    )
    .toBe('none');

  await page.locator('.nav a[href="/"]').click();
  await page.waitForURL(/\/$/);
  expect(await revealed(page)).toBe(slug);
});

test('a link without a plate changes the page at once', async ({ page }) => {
  await page.goto('/');
  await page.locator('.nav a[href="/about"]').click();
  await page.waitForURL('**/about');
  expect(await revealed(page)).toBe('none');
});

test.describe('with reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });

  test('nothing is carried', async ({ page }) => {
    await page.goto('/');
    const slug = await firstSlug(page);
    await page.locator(`.grid > li[data-slug="${slug}"] figure`).click();
    await page.waitForURL(`**/${slug}`);
    expect(await revealed(page)).toBe('none');
  });
});
