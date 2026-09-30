import type { Page } from '@playwright/test';
import { horizontalOverflow } from './helpers';
import { expect, test } from './test';

const WIDTHS = [320, 390, 1440] as const;

/** Pages and states, each checked at every width. `?t=catppuccin-mocha` shows the shared-theme line and the longest theme name. */
const STATES: { name: string; path: string; act?: (page: Page) => Promise<void> }[] = [
  { name: 'index', path: '/' },
  { name: 'index filtered, shared theme', path: '/?technique=drafting&q=s&t=catppuccin-mocha' },
  {
    name: 'index with the filter open',
    path: '/?other=any-screen',
    act: (page) => openFilter(page),
  },
  { name: 'index with nothing found', path: '/?q=zebra' },
  { name: 'index with the picker open', path: '/', act: (page) => openPicker(page) },
  { name: 'picker with both messages', path: '/', act: (page) => invalidPicker(page) },
  { name: 'loose-squares', path: '/loose-squares' },
  {
    name: 'loose-squares cropped to 32:9, shared theme',
    path: '/loose-squares?shape=32x9&crop=1&t=catppuccin-mocha',
  },
  { name: 'dither-moon at 9:19.5', path: '/dither-moon?shape=9x19.5' },
  { name: 'radar-sweep under light colors', path: '/radar-sweep?t=flexoki-light' },
  {
    name: 'radar-sweep with the picker open',
    path: '/radar-sweep',
    act: (page) => openPicker(page),
  },
  { name: 'about', path: '/about' },
  { name: 'not found', path: '/no-such-wallpaper' },
];

async function openPicker(page: Page): Promise<void> {
  await page.click('#theme-button');
  await expect(page.locator('#picker')).toBeVisible();
}

async function invalidPicker(page: Page): Promise<void> {
  await openPicker(page);
  await page.locator('#seed-fg').fill('#232221');
  await expect(page.locator('#faint-msg')).toBeVisible();
  await page.locator('#seed-accent').fill('#CF6A4');
  await page.locator('#seed-bg').focus();
  await expect(page.locator('#seed-msg')).toBeVisible();
}

async function openFilter(page: Page): Promise<void> {
  const details = page.locator('details.filter');
  if (!(await details.evaluate((d) => (d as HTMLDetailsElement).open)))
    await page.click('.filter > summary');
  await expect(details).toHaveAttribute('open');
}

test.describe('no sideways scrolling', () => {
  test.use({ colorScheme: 'dark' });

  for (const width of WIDTHS) {
    for (const s of STATES) {
      test(`${s.name} at ${width}px`, async ({ page }) => {
        await page.setViewportSize({ width, height: width < 500 ? 844 : 1000 });
        await page.goto(s.path);
        await page.evaluate(() => document.fonts.ready);
        await s.act?.(page);
        // Plates change height when their image arrives.
        if (await page.locator('.plate:visible').count())
          await expect(page.locator('.plate:visible > img').first()).toBeAttached();
        expect(await horizontalOverflow(page)).toEqual([]);
      });
    }
  }
});
