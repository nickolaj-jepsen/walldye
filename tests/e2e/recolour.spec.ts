import { expect, test, type Page } from '@playwright/test';
import { recolour, select } from '../../src/lib/recolour';
import { parseToken, type Seeds } from '../../src/lib/theme';
import { findColours } from '../../src/lib/tokenize';
import { colourDistance, decodeRgb, MANIFEST, maxSlotError, pixelDiff, pixelHex, platesSettled, readText, REFERENCE_PIECES, slotsOf } from './helpers';

/** What the index plate for `slug` should show under `seeds`: the committed 16:9 template through the TS recolour. */
function expected(slug: string, seeds: Seeds): string {
  const picked = select(slotsOf(slug), '16:9', seeds);
  return recolour(readText(`wallpapers/${slug}/build/${picked.entry.file}`), picked.entry, seeds);
}

/** The Python render of `slug` at 16:9 under `theme`, from tests/fixtures. */
function pythonRender(slug: string, theme: string): string {
  const r = MANIFEST.renders.find((x) => x.slug === slug && x.aspect === '16:9' && x.theme === theme);
  expect(r, `no 16:9 fixture for ${slug} under ${theme}`).toBeTruthy();
  return readText(r!.render);
}

/** Every way a visitor sets a theme: a preset, typed colours, a shared link. */
const ROUTES: { theme: string; how: string; set: (page: Page) => Promise<void> }[] = [
  {
    theme: 'nord',
    how: 'a preset',
    set: async (page) => {
      await page.goto('/');
      await page.click('#theme-button');
      await page.click('#picker button[data-preset=nord]');
    },
  },
  {
    theme: 'flexoki-light',
    how: 'a preset',
    set: async (page) => {
      await page.goto('/');
      await page.click('#theme-button');
      await page.click('#picker button[data-preset="flexoki-light"]');
    },
  },
  {
    theme: 'ffffff-000000-0000ff',
    how: 'typed colours',
    set: async (page) => {
      await page.goto('/');
      await page.click('#theme-button');
      for (const [k, typed, applied] of [['bg', 'fff', '#FFFFFF'], ['fg', '#000000', '#000000'], ['accent', '00f', '#0000FF']]) {
        await page.locator(`#seed-${k}`).fill(typed);
        await expect(page.locator('html')).toHaveAttribute('style', new RegExp(`--seed-${k}: ${applied}`));
      }
      await page.keyboard.press('Escape');
    },
  },
  {
    theme: '1c1b1b-dad8ce-cf6a4c',
    how: 'a shared link',
    set: async (page) => {
      await page.goto('/?t=1c1b1b-dad8ce-cf6a4c');
    },
  },
];

test.describe('index recolour', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 }, contextOptions: { reducedMotion: 'reduce' } });

  for (const { theme, how, set } of ROUTES) {
    test(`${theme} from ${how} recolours every plate like the Python render`, async ({ page }) => {
      const seeds = parseToken(theme)!;
      await set(page);
      await expect(page.locator('html')).toHaveAttribute('style', new RegExp(`--seed-bg: ${seeds.bg}`));

      // The SVG text: exactly the TS recolour, and within 2 units of the Python render slot by slot.
      const want = Object.fromEntries(REFERENCE_PIECES.map((slug) => [slug, expected(slug, seeds)]));
      await platesSettled(page, want);
      for (const slug of REFERENCE_PIECES) {
        expect(maxSlotError(want[slug], pythonRender(slug, theme)), `${slug} under ${theme}`).toBeLessThanOrEqual(2);
      }

      // The pixels: each plate as drawn, against the Python render drawn in its place by the same browser.
      for (const slug of REFERENCE_PIECES) {
        const plate = page.locator(`.grid > li[data-slug="${slug}"] .plate`);
        await plate.scrollIntoViewIfNeeded();
        const shown = decodeRgb(await plate.screenshot({ animations: 'disabled' }));
        await plate.evaluate(async (el, svg) => {
          const img = new Image(1920, 1080);
          img.src = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
          await img.decode();
          img.dataset.reference = '';
          img.style.cssText = 'position:absolute;top:0;left:0;transition:none';
          el.querySelector(':scope > img')!.after(img);
        }, pythonRender(slug, theme));
        const reference = decodeRgb(await plate.screenshot({ animations: 'disabled' }));
        await plate.evaluate((el) => el.querySelector('[data-reference]')?.remove());

        const diff = pixelDiff(shown, reference);
        test.info().annotations.push({ type: 'pixels', description: `${slug} ${theme}: max ${diff.max}, mean ${diff.mean.toFixed(3)}, >1 in ${diff.overOne} channels` });
        expect(diff.max, `${slug} under ${theme}: ${JSON.stringify(diff)}`).toBeLessThanOrEqual(3);
        // Inside the 1px frame the plate shows its background slot.
        const inset = Math.ceil(shown.width / 100);
        expect(colourDistance(pixelHex(shown, inset, inset), findColours(expected(slug, seeds))[0][2])).toBeLessThanOrEqual(1);
      }
    });
  }
});
