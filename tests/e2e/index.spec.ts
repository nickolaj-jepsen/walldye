import { expect, test, type Page } from '@playwright/test';

const visibleSlugs = (page: Page) => page.locator('.grid > li:not([hidden])').evaluateAll((lis) => lis.map((li) => (li as HTMLElement).dataset.slug));
const box = (page: Page, facet: string, value: string) => page.locator(`#facets input[name=${facet}][value="${value}"]`);
const countOf = (page: Page, facet: string, value: string) => page.locator(`#facets label.entry:has(input[name=${facet}][value="${value}"]) .count`);

test.describe('index filters', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('facets combine OR within and AND across, with live counts and the query string', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#result-count')).toHaveText('3 wallpapers');
    await expect(page.locator('.results-line .clear')).toBeHidden();

    await box(page, 'technique', 'drafting').check();
    await expect(page.locator('#result-count')).toHaveText('1 of 3 wallpapers');
    expect(await visibleSlugs(page)).toEqual(['schotter']);
    await expect(page.locator('.results-line .clear')).toBeVisible();
    expect(new URL(page.url()).search).toBe('?technique=drafting');
    // Another technique would add a piece; a subject that no drafting piece has is disabled.
    await expect(countOf(page, 'technique', 'dither')).toHaveText('1');
    await expect(box(page, 'subject', 'space')).toBeDisabled();

    await box(page, 'technique', 'dither').check();
    await expect(page.locator('#result-count')).toHaveText('2 of 3 wallpapers');
    expect(new URL(page.url()).search).toBe('?technique=dither&technique=drafting');
    await expect(box(page, 'subject', 'space')).toBeEnabled();

    await box(page, 'subject', 'space').check();
    expect(await visibleSlugs(page)).toEqual(['dither-moon']);

    // A filter never changes where a plate leads (docs/design.md, Detail: no `?from=`).
    await expect(page.locator('.grid > li[data-slug=dither-moon] > a')).toHaveAttribute('href', '/dither-moon');

    await page.click('.results-line .clear');
    await expect(page.locator('#result-count')).toHaveText('3 wallpapers');
    expect(new URL(page.url()).search).toBe('');
    await expect(page.locator('.grid > li[data-slug=dither-moon] > a')).toHaveAttribute('href', '/dither-moon');
  });

  test('search, sort and the empty state', async ({ page }) => {
    await page.goto('/');
    await page.fill('#q', 'NEES');
    await expect(page.locator('#result-count')).toHaveText('1 of 3 wallpapers');
    expect(await visibleSlugs(page)).toEqual(['schotter']);
    expect(new URL(page.url()).searchParams.get('q')).toBe('NEES');

    await page.fill('#q', 'zebra');
    await expect(page.locator('#result-count')).toHaveText('0 of 3 wallpapers');
    await expect(page.locator('.plates .empty')).toBeVisible();

    await page.fill('#q', '');
    await expect(page.locator('.plates .empty')).toBeHidden();
    await page.locator('#facets input[name=sort][value=title]').check({ force: true });
    const order = await page.locator('.grid > li').evaluateAll((lis) => lis.map((li) => (li as HTMLElement).dataset.slug));
    expect(order).toEqual(['dither-moon', 'radar-sweep', 'schotter']);
    expect(new URL(page.url()).search).toBe('?sort=title');
  });

  test('a filtered load fills the count before it becomes the live region', async ({ page }) => {
    await page.addInitScript(() => {
      const seen: string[] = [];
      (window as unknown as { seen: string[] }).seen = seen;
      new MutationObserver((records) => {
        for (const r of records) {
          const el = r.target instanceof Element ? r.target : r.target.parentElement;
          if (el?.id === 'result-count') seen.push(r.type === 'attributes' ? `role was ${r.oldValue ?? 'unset'}` : 'text');
        }
      }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['role'], attributeOldValue: true });
    });
    await page.goto('/?technique=drafting');
    await expect(page.locator('#result-count')).toHaveAttribute('role', 'status');
    await expect(page.locator('#result-count')).toHaveText('1 of 3 wallpapers');
    // The server's "3 wallpapers", then the client's "1 of 3 wallpapers", and only then the role.
    expect(await page.evaluate(() => (window as unknown as { seen: string[] }).seen)).toEqual(['text', 'text', 'role was unset']);
  });

  test('the query string restores the filter and ignores unknown values', async ({ page }) => {
    await page.goto('/?technique=instrument&technique=nonsense&sort=title&q=radar');
    await expect(box(page, 'technique', 'instrument')).toBeChecked();
    await expect(page.locator('#q')).toHaveValue('radar');
    await expect(page.locator('#facets input[name=sort][value=title]')).toBeChecked();
    await expect(page.locator('#result-count')).toHaveText('1 of 3 wallpapers');
    expect(new URL(page.url()).search).toBe('?q=radar&sort=title&technique=instrument');
  });

  test('the phone filter summary lists the active terms', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/?q=moon&other=any-screen');
    await expect(page.locator('details.filter')).not.toHaveAttribute('open');
    await expect(page.locator('.filter > summary .state')).toHaveText('“moon”, fits any screen');
  });
});

test.describe('index plates', () => {
  test('a plate whose recolour fails to load shows the template, then recolours on a retry', async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('walldye.theme', 'nord'));
    let failures = 0;
    await page.route('**/*.slots.json', (route) => (failures++ < 3 ? route.fulfill({ status: 503, body: '' }) : route.continue()));
    await page.goto('/');
    const srcs = () => page.locator('.grid .plate > img').evaluateAll((imgs) => imgs.map((i) => i.getAttribute('src') ?? ''));
    // The untouched template stands in, with the alt text, until the retry.
    await expect.poll(async () => (await srcs()).length).toBe(3);
    await expect(page.locator('.grid .plate > img').first()).toHaveAttribute('alt', /./);
    await expect.poll(async () => (await srcs()).every((s) => s.startsWith('blob:')), { timeout: 10_000 }).toBe(true);
  });

  test('every plate gets an image with the description as alt text', async ({ page }) => {
    await page.goto('/');
    const img = page.locator('.grid > li[data-slug=schotter] .plate > img');
    await expect(img).toHaveAttribute('alt', /^Twenty-nine columns/);
    await expect(img).toHaveAttribute('width', '1920');
  });
});
