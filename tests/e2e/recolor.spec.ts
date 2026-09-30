import { recolor, select } from '../../src/lib/recolor';
import { parseToken } from '../../src/lib/theme';
import { platesSettled, REFERENCE_PIECES, readText, slotsOf } from './helpers';
import { expect, test } from './test';

// vitest checks recolor() against the Python renders; this checks the index repaints with it.
test.use({
  colorScheme: 'dark',
  viewport: { width: 1440, height: 1000 },
  contextOptions: { reducedMotion: 'reduce' },
});

test('choosing a preset repaints the plates with the recolored templates', async ({ page }) => {
  const seeds = parseToken('nord')!;
  await page.goto('/');
  await page.click('#theme-button');
  await page.click('#picker button[data-preset=nord]');
  await expect(page.locator('html')).toHaveAttribute('style', new RegExp(`--seed-bg: ${seeds.bg}`));
  const want = Object.fromEntries(
    REFERENCE_PIECES.map((slug) => {
      const picked = select(slotsOf(slug), '16:9', seeds);
      return [
        slug,
        recolor(readText(`wallpapers/${slug}/build/${picked.entry.file}`), picked.entry, seeds),
      ];
    }),
  );
  await platesSettled(page, want);
});
