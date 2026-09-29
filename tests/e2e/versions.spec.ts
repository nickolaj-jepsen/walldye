import { readFile } from 'node:fs/promises';
import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';
import { focusPosition } from '../../src/client/export/shape';
import { type CatalogueVersion, publishedPieces, templateUrl } from './helpers';

/**
 * Versions on the real catalogue. PIECE is the first published piece with a published named
 * version, a portrait template of its own for every version, and a crop at 16:10; PLAIN is the
 * first published piece without versions, preferring a fan work so the disclaimer shows too.
 */
const PIECES = publishedPieces();
const PIECE = PIECES.find(
  (p) =>
    p.versions.length > 1 &&
    p.versions.every((v) => v.aspects.includes('10:16') && !v.aspects.includes('16:10')),
);
const PLAIN = PIECES.filter((p) => p.versions.length === 1).sort(
  (a, b) => Number(!a.franchise) - Number(!b.franchise),
)[0];

const version = (page: Page, label: string) =>
  page.getByRole('radio', { name: label, exact: true });
const choose = (page: Page, label: string) => version(page, label).check({ force: true });
const pick = (page: Page, name: string, value: string) =>
  page.locator(`#export input[name=${name}][value="${value}"]`).check({ force: true });
// The newest image: an old one stays under it until the fade ends.
const plateImg = (page: Page) => page.locator('.spread .plate > img').last();

test.describe('versions', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });
  test.skip(!PIECE, 'no published piece with versions, a portrait template and a 16:10 crop');
  const { slug, versions, license } = PIECE ?? { slug: '', versions: [], license: '' };
  const [base, other] = versions as [CatalogueVersion, CatalogueVersion];
  const named = `${slug}--${other?.name}`;

  test('the index shows one plate per design, counting its published versions', async ({
    page,
  }) => {
    await page.goto('/');
    await expect(page.locator('.grid > li')).toHaveCount(PIECES.length);
    await expect(page.locator(`#v-${slug}`)).toHaveText(`${versions.length} versions`);
    await expect(page.locator(`.grid > li[data-slug=${slug}] > a`)).toHaveAttribute(
      'aria-describedby',
      `v-${slug}`,
    );
    await expect(page.locator(`.grid > li[data-slug=${PLAIN.slug}] .v`)).toHaveCount(0);
    await page.locator(`.grid > li[data-slug=${slug}]`).scrollIntoViewIfNeeded();
    await expect(page.locator(`.grid > li[data-slug=${slug}] .plate > img`)).toHaveAttribute(
      'src',
      templateUrl(base.slots, '16:9'),
    );
  });

  test('choosing a version swaps the plate, the description and the names, and writes ?v=', async ({
    page,
  }) => {
    await page.goto(`/${slug}`);
    await expect(page.locator('#versions-h')).toHaveText('Versions');
    await expect(page.getByRole('radiogroup', { name: 'Versions' }).getByRole('radio')).toHaveCount(
      versions.length,
    );
    await expect(version(page, base.label)).toBeChecked();
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl(base.slots, '16:9'));
    await expect(page.locator('#download-name')).toHaveText(`${slug}-fireproof-2560x1440.png`);

    await choose(page, other.label);
    expect(new URL(page.url()).search).toBe(`?v=${other.name}`);
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl(other.slots, '16:9'));
    await expect(plateImg(page)).toHaveAttribute('alt', other.description);
    await expect(page.locator('#desc')).toHaveText(other.description);
    await expect(page.locator('#download-name')).toHaveText(`${named}-fireproof-2560x1440.png`);
    await expect(page.locator('#run-render')).toHaveText(
      `uv run walldye render ${slug} --variant ${other.name} --theme fireproof -o ${named}-fireproof-16x9.svg`,
    );
    // One page per design: the version never reaches the canonical address or the social card.
    await expect(page.locator('link[rel=canonical]')).toHaveAttribute(
      'href',
      `https://walldye.com/${slug}`,
    );
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
      'content',
      `https://walldye.com/og/${slug}.jpg`,
    );
    await expect(page.locator('meta[name=description]')).toHaveAttribute(
      'content',
      base.description,
    );
    await expect(page.locator('meta[property="og:image:alt"]')).toHaveAttribute(
      'content',
      base.description,
    );

    await page.reload();
    await expect(version(page, other.label)).toBeChecked();
    await expect(page.locator('#desc')).toHaveText(other.description);

    await choose(page, base.label);
    expect(new URL(page.url()).search).toBe('');
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl(base.slots, '16:9'));
    await expect(page.locator('#desc')).toHaveText(base.description);
    await expect(page.locator('#run-render')).toHaveText(
      `uv run walldye render ${slug} --theme fireproof -o ${slug}-fireproof-16x9.svg`,
    );
  });

  test('theme and shape stay; a placed crop stays and an unplaced one follows the focus', async ({
    page,
  }) => {
    await page.goto(`/${slug}?t=nord`);
    await pick(page, 'asp', '16:10');
    const at = (v: CatalogueVersion) => String(focusPosition('16:10', v.slots.focus));
    await expect(page.locator('#crop')).toHaveValue(at(base));

    await choose(page, other.label);
    await expect(page.locator('#crop')).toHaveValue(at(other));
    expect(new URL(page.url()).search).toBe(`?v=${other.name}&shape=16x10`);
    await expect(page.locator('#download-name')).toHaveText(`${named}-nord-2560x1600.png`);
    await expect(plateImg(page)).toHaveAttribute('src', /^blob:/);

    await page.locator('#crop').evaluate((el) => {
      (el as HTMLInputElement).value = '0.9';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await choose(page, base.label);
    await expect(page.locator('#crop')).toHaveValue('0.9');
    expect(new URL(page.url()).search).toBe('?shape=16x10&crop=0.9');
    await expect(page.locator('#export input[name=asp][value="16:10"]')).toBeChecked();
    await expect(page.locator('#download-name')).toHaveText(`${slug}-nord-2560x1600.png`);
  });

  test("a native shape shows that version's own template, and the export carries the version", async ({
    page,
  }) => {
    await page.goto(`/${slug}?v=${other.name}`);
    await pick(page, 'asp', '10:16');
    await expect(plateImg(page)).toHaveAttribute('data-aspect', '10:16');
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl(other.slots, '10:16'));
    await expect(page.locator('#cell-note')).toBeVisible({ visible: other.slots.cells.length > 0 });

    await pick(page, 'fmt', 'svg');
    await expect(page.locator('#download-name')).toHaveText(`${named}-fireproof-10x16.svg`);
    const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#download')]);
    expect(dl.suggestedFilename()).toBe(`${named}-fireproof-10x16.svg`);
    const svg = await readFile((await dl.path())!, 'utf8');
    expect(svg).toContain(
      `<desc>walldye.com/${slug}?v=${other.name} · ${license} · theme fireproof</desc>`,
    );

    await choose(page, base.label);
    await pick(page, 'fmt', 'png');
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl(base.slots, '10:16'));
  });

  test('an unknown ?v= shows the default, and every published version is served', async ({
    page,
    request,
  }) => {
    await page.goto(`/${slug}?v=nope`);
    await expect(version(page, base.label)).toBeChecked();
    await expect(page.locator('#desc')).toHaveText(base.description);
    await expect(plateImg(page)).toHaveAttribute('src', templateUrl(base.slots, '16:9'));
    await expect(page.locator('#download-name')).toHaveText(`${slug}-fireproof-2560x1440.png`);
    const shown = JSON.parse(
      (await page.locator('.spread .plate').getAttribute('data-variants'))!,
    ) as Record<string, unknown>;
    expect(Object.keys(shown)).toEqual(versions.map((v) => v.name));
    for (const v of versions)
      expect((await request.get(templateUrl(v.slots, '16:9'))).status()).toBe(200);
  });

  test('a design without versions has no switcher, and the sitemap lists each design once', async ({
    page,
    request,
  }) => {
    await page.goto(`/${PLAIN.slug}`);
    await expect(page.locator('#versions')).toHaveCount(0);
    if (PLAIN.franchise) {
      const { title, owner } = PLAIN.franchise;
      await expect(page.locator('.label .licence')).toHaveText(
        `Unofficial fan tribute, not affiliated with or endorsed by ${owner}. ${title} and its characters are trademarks of their owners. Non-commercial; contact takedown@walldye.com for takedown.`,
      );
      await expect(page.locator('.label .licence a')).toHaveAttribute(
        'href',
        'mailto:takedown@walldye.com',
      );
    }
    await expect(page.locator('.spread .plate')).not.toHaveAttribute('data-variants');
    await expect(page.locator('.controls')).toHaveAttribute('aria-label', 'Colours and export');
    const sitemap = await (await request.get('/sitemap-0.xml')).text();
    for (const s of [slug, PLAIN.slug]) {
      expect(
        sitemap
          .match(/<loc>[^<]*<\/loc>/g)
          ?.filter((l) => l === `<loc>https://walldye.com/${s}</loc>`),
      ).toHaveLength(1);
    }
  });

  test('the switcher passes axe', async ({ page }) => {
    await page.goto(`/${slug}?v=${other.name}`);
    await page.evaluate(() => document.fonts.ready);
    const found = await new AxeBuilder({ page })
      .include('.controls')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'])
      .analyze();
    expect(
      found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`),
    ).toEqual([]);
  });
});
