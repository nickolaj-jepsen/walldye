import { readFile } from 'node:fs/promises';
import AxeBuilder from '@axe-core/playwright';
import { test as base, expect, type Page } from '@playwright/test';
import { focusPosition } from '../../src/scripts/export-svg';
import { fixtureSite, PIECES, templateUrl } from './fixture-site';

/** Versions on the fixture site (tests/e2e/fixture-site.ts): moon-phase has a published and a draft variant. */
const test = base.extend<object, { site: string }>({
  site: [
    async ({}, use, workerInfo) => {
      const site = await fixtureSite(workerInfo.project.outputDir);
      await use(site.url);
      await site.close();
    },
    { scope: 'worker', timeout: 180_000 },
  ],
  baseURL: async ({ site }, use) => use(site),
});

const MOON = PIECES['moon-phase'];
const FULL = 'A full moon over a flat horizon, drawn as a ring around a disc.';
const CRESCENT = 'A crescent moon low over a flat horizon, cut from two discs.';

const version = (page: Page, label: string) => page.getByRole('radio', { name: label });
const choose = (page: Page, label: string) => version(page, label).check({ force: true });
const pick = (page: Page, name: string, value: string) => page.locator(`#export input[name=${name}][value="${value}"]`).check({ force: true });
// The newest image: an old one stays under it until the fade ends.
const plateImg = (page: Page) => page.locator('.spread .plate > img').last();

test.describe('versions', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('the index shows one plate per design, counting its published versions', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.grid > li')).toHaveCount(2);
    await expect(page.locator('#v-moon-phase')).toHaveText('2 versions');
    await expect(page.locator('.grid > li[data-slug=moon-phase] > a')).toHaveAttribute('aria-describedby', 'v-moon-phase');
    await expect(page.locator('.grid > li[data-slug=grid-plain] .v')).toHaveCount(0);
    await expect(page.locator('.grid > li[data-slug=moon-phase] .plate > img')).toHaveAttribute('src', templateUrl('moon-phase', 'default', '16:9'));
  });

  test('choosing a version swaps the plate, the description and the names, and writes ?v=', async ({ page }) => {
    await page.goto('/moon-phase');
    await expect(page.locator('#versions-h')).toHaveText('Versions');
    await expect(page.getByRole('radiogroup', { name: 'Versions' }).getByRole('radio')).toHaveCount(2);
    await expect(version(page, 'Full moon')).toBeChecked();
    await expect(version(page, 'New moon')).toHaveCount(0);
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl('moon-phase', 'default', '16:9'));
    await expect(page.locator('#download-name')).toHaveText('moon-phase-fireproof-2560x1440.png');

    await choose(page, 'Crescent');
    expect(new URL(page.url()).search).toBe('?v=crescent');
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl('moon-phase', 'crescent', '16:9'));
    await expect(plateImg(page)).toHaveAttribute('alt', CRESCENT);
    await expect(page.locator('#desc')).toHaveText(CRESCENT);
    await expect(page.locator('#download-name')).toHaveText('moon-phase--crescent-fireproof-2560x1440.png');
    await expect(page.locator('#run-render')).toHaveText('uv run walldye render moon-phase --variant crescent --theme fireproof -o moon-phase--crescent-fireproof-16x9.svg');
    // One page per design: the version never reaches the canonical address or the social card.
    await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', 'https://walldye.com/moon-phase');
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', 'https://walldye.com/og/moon-phase.jpg');
    await expect(page.locator('meta[name=description]')).toHaveAttribute('content', FULL);

    await page.reload();
    await expect(version(page, 'Crescent')).toBeChecked();
    await expect(page.locator('#desc')).toHaveText(CRESCENT);

    await choose(page, 'Full moon');
    expect(new URL(page.url()).search).toBe('');
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl('moon-phase', 'default', '16:9'));
    await expect(page.locator('#desc')).toHaveText(FULL);
    await expect(page.locator('#run-render')).toHaveText('uv run walldye render moon-phase --theme fireproof -o moon-phase-fireproof-16x9.svg');
  });

  test('theme and shape stay; a placed crop stays and an unplaced one follows the focus', async ({ page }) => {
    await page.goto('/moon-phase?t=nord');
    await pick(page, 'asp', '16:10');
    const at = (name: string) => String(focusPosition('16:10', MOON.versions[name].focus));
    await expect(page.locator('#crop')).toHaveValue(at('default'));

    await choose(page, 'Crescent');
    await expect(page.locator('#crop')).toHaveValue(at('crescent'));
    expect(new URL(page.url()).search).toBe(`?v=crescent&shape=16x10&crop=${at('crescent')}`);
    await expect(page.locator('#download-name')).toHaveText('moon-phase--crescent-nord-2560x1600.png');
    await expect(plateImg(page)).toHaveAttribute('src', /^blob:/);

    await page.locator('#crop').evaluate((el) => {
      (el as HTMLInputElement).value = '0.9';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await choose(page, 'Full moon');
    await expect(page.locator('#crop')).toHaveValue('0.9');
    expect(new URL(page.url()).search).toBe('?shape=16x10&crop=0.9');
    await expect(page.locator('#export input[name=asp][value="16:10"]')).toBeChecked();
    await expect(page.locator('#download-name')).toHaveText('moon-phase-nord-2560x1600.png');
  });

  test("a native shape shows that version's own template, and the export carries the version", async ({ page }) => {
    await page.goto('/moon-phase?v=crescent');
    await pick(page, 'asp', '10:16');
    await expect(plateImg(page)).toHaveAttribute('data-aspect', '10:16');
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl('moon-phase', 'crescent', '10:16'));
    // The crescent's slots.json has cells, the full moon's has none.
    await expect(page.locator('#cell-note')).toHaveText('At this size the squares come out 8 or 9 pixels wide.');

    await pick(page, 'fmt', 'svg');
    await expect(page.locator('#download-name')).toHaveText('moon-phase--crescent-fireproof-10x16.svg');
    const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#download')]);
    expect(dl.suggestedFilename()).toBe('moon-phase--crescent-fireproof-10x16.svg');
    const svg = await readFile((await dl.path())!, 'utf8');
    expect(svg).toContain('<title>Moon phase</title><desc>walldye.com/moon-phase?v=crescent · CC0-1.0 · theme fireproof</desc>');
    expect(svg).toContain(`cx="${1080 * 0.36}" cy="${1728 * 0.6}" r="150"`);

    await choose(page, 'Full moon');
    await pick(page, 'fmt', 'png');
    await expect(page.locator('#cell-note')).toBeHidden();
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl('moon-phase', 'default', '10:16'));
  });

  test('a draft or unknown ?v= shows the default, and draft templates are not published', async ({ page, request }) => {
    for (const v of ['new-moon', 'nope']) {
      await page.goto(`/moon-phase?v=${v}`);
      await expect(version(page, 'Full moon')).toBeChecked();
      await expect(page.locator('#desc')).toHaveText(FULL);
      await expect(plateImg(page)).toHaveAttribute('src', templateUrl('moon-phase', 'default', '16:9'));
      await expect(page.locator('#download-name')).toHaveText('moon-phase-fireproof-2560x1440.png');
    }
    const variants = JSON.parse((await page.locator('.spread .plate').getAttribute('data-variants'))!) as Record<string, unknown>;
    expect(Object.keys(variants)).toEqual(['default', 'crescent']);
    expect((await request.get(templateUrl('moon-phase', 'crescent', '16:9'))).status()).toBe(200);
    expect((await request.get(templateUrl('moon-phase', 'new-moon', '16:9'))).status()).toBe(404);
  });

  test('a design without versions has no switcher, and the sitemap lists each design once', async ({ page, request }) => {
    await page.goto('/grid-plain');
    await expect(page.locator('#versions')).toHaveCount(0);
    await expect(page.locator('.label .licence')).toHaveText(
      'Unofficial fan tribute, not affiliated with or endorsed by Example Games. Graph Paper Quest and its characters are trademarks of their owners. Non-commercial; contact takedown@walldye.com for takedown.',
    );
    await expect(page.locator('.spread .plate')).not.toHaveAttribute('data-variants');
    await expect(page.locator('.controls')).toHaveAttribute('aria-label', 'Colours and export');
    const sitemap = await (await request.get('/sitemap-0.xml')).text();
    expect(sitemap.match(/<loc>[^<]*<\/loc>/g)?.filter((l) => /moon-phase|grid-plain/.test(l))).toEqual([
      '<loc>https://walldye.com/grid-plain</loc>',
      '<loc>https://walldye.com/moon-phase</loc>',
    ]);
  });

  test('the switcher passes axe', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'the axe sweep runs on Chromium');
    await page.goto('/moon-phase?v=crescent');
    await page.evaluate(() => document.fonts.ready);
    const found = await new AxeBuilder({ page }).include('.controls').withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze();
    expect(found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
  });
});
