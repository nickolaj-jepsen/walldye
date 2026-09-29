import { expect, type Page, test } from '@playwright/test';
import YAML from 'yaml';
import { publishedPieces, readText, templateUrl } from './helpers';

/**
 * Browsing aids: the index's shape and color row, the picker's theme import, and on detail pages
 * the version pictures, "See also" and the closed source listing. A PORTRAIT piece has a 9:19.5
 * template of its own and a CROPPED one does not.
 */
const PIECES = publishedPieces();
const hasPortrait = (p: (typeof PIECES)[number]) => p.versions[0].aspects.includes('9:19.5');
const PORTRAIT = PIECES.find(hasPortrait);
const CROPPED = PIECES.find((p) => !hasPortrait(p));
const VERSIONED = PIECES.find((p) => p.versions.length > 1);

const plateImg = (page: Page, slug: string) =>
  page.locator(`.grid > li[data-slug="${slug}"] .plate > img`).last();
const link = (page: Page, slug: string) => page.locator(`.grid > li[data-slug="${slug}"] > a`);

/** Pastes `text` into `selector` as the clipboard would. */
const paste = (page: Page, selector: string, text: string) =>
  page.locator(selector).evaluate((el, t) => {
    const data = new DataTransfer();
    data.setData('text/plain', t);
    el.dispatchEvent(
      new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }),
    );
  }, text);

test.describe('index shape', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });
  test.skip(!PORTRAIT || !CROPPED, 'needs a piece with a 9:19.5 template and one without');

  test('a shape shows own templates or focus crops, and plates open in it', async ({ page }) => {
    const portrait = PORTRAIT!.slug;
    const cropped = CROPPED!.slug;
    await page.goto('/?shape=9x19.5');
    await expect(page.locator('section.plates')).toHaveAttribute('data-shape', '9:19.5');
    await expect(page.locator('#facets input[name=shape][value="9x19.5"]')).toBeChecked();

    await page.locator(`.grid > li[data-slug="${portrait}"]`).scrollIntoViewIfNeeded();
    // A tall plate reads slots.json before its template, which can take a while under a full run.
    const loads = { timeout: 15_000 };
    await expect(plateImg(page, portrait)).toHaveAttribute(
      'src',
      templateUrl(PORTRAIT!.versions[0].slots, '9:19.5'),
      loads,
    );
    await expect(link(page, portrait)).toHaveAttribute('href', `/${portrait}?shape=9x19.5`);

    await page.locator(`.grid > li[data-slug="${cropped}"]`).scrollIntoViewIfNeeded();
    const img = plateImg(page, cropped);
    await expect(img).toHaveAttribute('data-aspect', '16:9', loads);
    expect(await img.evaluate((el) => getComputedStyle(el).objectFit)).toBe('cover');
    const box = await img.boundingBox();
    expect(box!.height / box!.width).toBeGreaterThan(2);

    await page.locator('#facets input[name=shape][value="16x9"]').check({ force: true });
    expect(new URL(page.url()).search).toBe('');
    await expect(link(page, cropped)).toHaveAttribute('href', `/${cropped}`);
    await expect(page.locator('section.plates')).toHaveAttribute('data-shape', '16:9');
  });

  test('clear keeps the shape', async ({ page }) => {
    await page.goto('/?shape=21x9&q=a');
    await page.click('.results-line .clear');
    // The reset applies a task later, so wait for the address rather than read it at once.
    await expect.poll(() => new URL(page.url()).search).toBe('?shape=21x9');
  });
});

test.describe('index shape on a phone', () => {
  test.use({
    colorScheme: 'dark',
    viewport: { width: 390, height: 844 },
    contextOptions: { screen: { width: 390, height: 844 } },
    hasTouch: true,
  });

  test("starts in the phone's shape without writing it", async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'pointer: coarse follows hasTouch in Chromium only');
    await page.goto('/');
    await expect(page.locator('section.plates')).toHaveAttribute('data-shape', '9:19.5');
    await expect(page.locator('#facets input[name=shape][value="9x19.5"]')).toBeChecked();
    expect(new URL(page.url()).search).toBe('');
    const first = await page.locator('.grid > li').first().getAttribute('data-slug');
    await expect(link(page, first!)).toHaveAttribute('href', `/${first}`);
  });
});

test.describe('index order', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('the index opens on the featured pieces, in featured.yaml order', async ({ page }) => {
    const published = new Set(PIECES.map((p) => p.slug));
    const featured = (YAML.parse(readText('featured.yaml')) as string[]).filter((s) =>
      published.has(s),
    );
    test.skip(featured.length === 0, 'nothing on featured.yaml is published');
    await page.goto('/');
    await expect(page.locator('#facets input[name=sort][value=featured]')).toBeChecked();
    const order = await page
      .locator('.grid > li')
      .evaluateAll((lis) => lis.map((li) => (li as HTMLElement).dataset.slug));
    expect(order.slice(0, featured.length)).toEqual(featured);
    expect(new URL(page.url()).search).toBe('');
  });
});

test.describe('colors', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('the row over the grid applies and saves a preset', async ({ page }) => {
    await page.goto('/');
    const nord = page.locator('.themes button[data-preset=nord]');
    await expect(page.locator('.themes button[data-family=fireproof]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await nord.click();
    await expect(page.locator('.themes button[data-family=fireproof]')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'nord');
    await expect(nord).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#picker button[data-preset=nord]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(await page.evaluate(() => localStorage.getItem('walldye.theme'))).toBe('nord');
  });

  test('a family in the row shows and picks its theme for the system scheme', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/');
    const gruvbox = page.locator('.themes button[data-family=gruvbox]');
    await expect(gruvbox.locator('.for-light')).toBeVisible();
    await expect(gruvbox.locator('.for-dark')).toBeHidden();
    await gruvbox.click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'gruvbox-light');
    await expect(gruvbox).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#picker button[data-family=gruvbox]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(gruvbox.locator('.for-dark')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'gruvbox-dark');
  });

  test('a pasted terminal theme fills the colors', async ({ page, browserName }) => {
    test.skip(browserName === 'firefox', 'Firefox empties clipboardData on synthetic paste events');
    await page.goto('/about');
    await page.click('#theme-button');
    await paste(page, '#theme-import', 'hello');
    await expect(page.locator('#import-msg')).toBeVisible();
    await paste(
      page,
      '#theme-import',
      'background #101820\nforeground #F0F0E0\ncolor1 #E04040\ncolor4 #202830',
    );
    await expect(page.locator('#import-msg')).toBeHidden();
    await expect(page.locator('#seed-bg')).toHaveValue('#101820');
    await expect(page.locator('#seed-accent')).toHaveValue('#E04040');
    await expect(page.locator('html')).toHaveAttribute('data-theme', '101820-f0f0e0-e04040');
  });
});

test.describe('detail extras', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('each version shows its own picture, hidden from its radio name', async ({ page }) => {
    test.skip(!VERSIONED, 'no published piece with versions');
    await page.goto(`/${VERSIONED!.slug}`);
    const thumbs = page.locator('#versions .thumb');
    await expect(thumbs).toHaveCount(VERSIONED!.versions.length);
    await expect(thumbs.first()).toHaveAttribute('aria-hidden', 'true');
    for (const [i, v] of VERSIONED!.versions.entries()) {
      await expect(thumbs.nth(i).locator('img').last()).toHaveAttribute(
        'src',
        templateUrl(v.slots, '16:9'),
      );
    }
  });

  test('See also follows the page shape, and the source listing starts closed', async ({
    page,
  }) => {
    await page.goto('/schotter');
    const related = page.locator('section.related .grid > li');
    const n = await related.count();
    expect(n).toBeGreaterThan(0);
    expect(n).toBeLessThanOrEqual(4);
    await expect(page.locator('section.related li[data-slug=schotter]')).toHaveCount(0);
    const other = await related.first().getAttribute('data-slug');
    await page.locator('#export input[name=asp][value="9:19.5"]').check({ force: true });
    await expect(page.locator('section.related')).toHaveAttribute('data-shape', '9:19.5');
    await expect(related.first().locator('> a')).toHaveAttribute('href', `/${other}?shape=9x19.5`);

    await expect(page.locator('.appendix')).not.toHaveAttribute('open');
    await expect(page.locator('.listing')).toBeHidden();
    await page.locator('.appendix > summary').click();
    await expect(page.locator('.listing')).toBeVisible();
  });
});
