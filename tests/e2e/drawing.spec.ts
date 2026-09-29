import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { slotsOf, templateUrl } from './helpers';

/** Drawing in the browser, on radar-sweep: a new draw changes it, and meta.yaml labels its sweep. */
test.describe('drawing', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });
  // The first draw downloads and boots Pyodide.
  test.setTimeout(180_000);

  test('Draw another draws the plate here, names the files and the address; a link with an edit opens drawn', async ({ page }) => {
    const template = templateUrl(slotsOf('radar-sweep'), '16:9');
    const plateImg = page.locator('.spread .plate > img').last();
    await page.goto('/radar-sweep');
    await expect(plateImg).toHaveAttribute('src', template);
    await expect(page.getByRole('button', { name: 'Back to the original' })).toBeHidden();

    await page.getByRole('button', { name: 'Draw another' }).click();
    await expect(plateImg).toHaveAttribute('src', /^blob:/, { timeout: 150_000 });
    const draw = new URL(page.url()).searchParams.get('draw') ?? '';
    expect(draw).toMatch(/^\d+$/);
    await expect(page.locator('#download-name')).toHaveText(`radar-sweep-draw${draw}-fireproof-2560x1440.png`);
    await expect(page.locator('#run-render')).toHaveText(
      `uv run walldye render radar-sweep --set seed=${draw} --theme fireproof -o radar-sweep-draw${draw}-fireproof-16x9.svg`,
    );

    await page.locator('#export input[name=fmt][value=svg]').check({ force: true });
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#download').click()]);
    expect(download.suggestedFilename()).toBe(`radar-sweep-draw${draw}-fireproof-16x9.svg`);
    expect(await readFile(await download.path(), 'utf8')).toContain(`radar-sweep?draw=${draw}`);

    await page.getByRole('button', { name: 'Back to the original' }).click();
    await expect(plateImg).toHaveAttribute('src', template);
    expect(new URL(page.url()).search).toBe('');
    await expect(page.getByRole('button', { name: 'Draw another' })).toBeFocused();

    await page.goto('/radar-sweep?sweep=200');
    await expect(page.getByLabel('Sweep')).toHaveValue('200');
    await expect(page.locator('[data-readout=sweep]')).toHaveText('200°');
    await expect(page.locator('.spread .plate > img').last()).toHaveAttribute('src', /^blob:/, { timeout: 150_000 });
  });
});
