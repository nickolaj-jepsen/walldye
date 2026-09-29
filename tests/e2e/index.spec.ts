import { expect, type Page, test } from '@playwright/test';
import {
  countFor,
  type Filterable,
  type FilterState,
  matches,
  ordered,
} from '../../src/client/index/filter';
import type { SortOrder } from '../../src/lib/content';

const visibleSlugs = (page: Page) =>
  page
    .locator('.grid > li:not([hidden])')
    .evaluateAll((lis) => lis.map((li) => (li as HTMLElement).dataset.slug));
const box = (page: Page, facet: string, value: string) =>
  page.locator(`#facets input[name=${facet}][value="${value}"]`);
const countOf = (page: Page, facet: string, value: string) =>
  page.locator(`#facets label.entry:has(input[name=${facet}][value="${value}"]) .count`);

/** Every index plate as the filter reads it from the server-rendered list; the expectations below come from these and filter.ts, which the unit tests cover. */
async function catalog(page: Page): Promise<Filterable[]> {
  const rows = await page.locator('.grid > li').evaluateAll((lis) =>
    lis.map((li) => {
      const d = (li as HTMLElement).dataset;
      return {
        slug: d.slug ?? '',
        title: d.title ?? '',
        added: d.added ?? '',
        views: Number(d.views ?? 0),
        recent: Number(d.recent ?? 0),
        facets: d.facets ?? '',
        search: d.search ?? '',
      };
    }),
  );
  return rows.map((r) => ({ ...r, facets: new Set(r.facets.split(' ').filter(Boolean)) }));
}

/** A filter state; without `sort` the grid keeps the server's order, the build's first. */
const state = (
  facets: Record<string, string[]>,
  q = '',
  sort?: SortOrder,
): FilterState & { kept: boolean } => ({
  q,
  sort: sort ?? 'newest',
  shape: '16:9',
  facets: new Map(Object.entries(facets).map(([f, vs]) => [f, new Set(vs)])),
  kept: sort === undefined,
});
/** The slugs `s` shows, in order. */
const shown = (items: Filterable[], s: ReturnType<typeof state>) => {
  const hits = items.filter((it) => matches(it, s));
  return (s.kept ? hits : ordered(hits, s.sort)).map((it) => it.slug);
};
/** The results line for `n` of `total` plates. */
const results = (n: number, total: number) =>
  n === total ? `${total} wallpapers` : `${n} of ${total} wallpapers`;

test.describe('index filters', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('facets combine OR within and AND across, with live counts and the query string', async ({
    page,
  }) => {
    await page.goto('/');
    const items = await catalog(page);
    const total = items.length;
    await expect(page.locator('#result-count')).toHaveText(results(total, total));
    await expect(page.locator('.results-line .clear')).toBeHidden();

    const drafting = state({ technique: ['drafting'] });
    await box(page, 'technique', 'drafting').check();
    const onlyDrafting = shown(items, drafting);
    expect(onlyDrafting).toContain('schotter');
    await expect(page.locator('#result-count')).toHaveText(results(onlyDrafting.length, total));
    expect(await visibleSlugs(page)).toEqual(onlyDrafting);
    await expect(page.locator('.results-line .clear')).toBeVisible();
    expect(new URL(page.url()).search).toBe('?technique=drafting');
    // Another technique would add pieces; a subject that no drafting piece has is disabled until one that has it is added.
    const dither = countFor(items, drafting, 'technique', 'dither');
    expect(dither).toBeGreaterThan(0);
    await expect(countOf(page, 'technique', 'dither')).toHaveText(String(dither));
    const both = state({ technique: ['dither', 'drafting'] });
    const subjects = await page
      .locator('#facets input[name=subject]')
      .evaluateAll((els) => els.map((e) => (e as HTMLInputElement).value));
    const subject = subjects.find(
      (v) =>
        countFor(items, drafting, 'subject', v) === 0 && countFor(items, both, 'subject', v) > 0,
    );
    expect(subject, 'a subject some dithered piece has and no drafting one').toBeDefined();
    await expect(box(page, 'subject', subject!)).toBeDisabled();

    await box(page, 'technique', 'dither').check();
    await expect(page.locator('#result-count')).toHaveText(
      results(shown(items, both).length, total),
    );
    expect(new URL(page.url()).search).toBe('?technique=dither&technique=drafting');
    await expect(box(page, 'subject', subject!)).toBeEnabled();

    await box(page, 'subject', subject!).check();
    const narrowed = shown(
      items,
      state({ technique: ['dither', 'drafting'], subject: [subject!] }),
    );
    expect(narrowed.length).toBeGreaterThan(0);
    expect(await visibleSlugs(page)).toEqual(narrowed);

    // A filter never changes where a plate leads (no `?from=`).
    const slug = narrowed[0];
    await expect(page.locator(`.grid > li[data-slug="${slug}"] > a`)).toHaveAttribute(
      'href',
      `/${slug}`,
    );

    await page.click('.results-line .clear');
    await expect(page.locator('#result-count')).toHaveText(results(total, total));
    expect(new URL(page.url()).search).toBe('');
    await expect(page.locator(`.grid > li[data-slug="${slug}"] > a`)).toHaveAttribute(
      'href',
      `/${slug}`,
    );
  });

  test('search, sort and the empty state', async ({ page }) => {
    await page.goto('/');
    const items = await catalog(page);
    const total = items.length;
    await page.fill('#q', 'NEES');
    const nees = shown(items, state({}, 'NEES'));
    expect(nees).toContain('schotter');
    await expect(page.locator('#result-count')).toHaveText(results(nees.length, total));
    expect(await visibleSlugs(page)).toEqual(nees);
    expect(new URL(page.url()).searchParams.get('q')).toBe('NEES');

    await page.fill('#q', 'zebra');
    await expect(page.locator('#result-count')).toHaveText(`0 of ${total} wallpapers`);
    await expect(page.locator('.plates .empty')).toBeVisible();

    await page.fill('#q', '');
    await expect(page.locator('.plates .empty')).toBeHidden();
    await page.locator('#facets input[name=sort][value=title]').check({ force: true });
    const order = await page
      .locator('.grid > li')
      .evaluateAll((lis) => lis.map((li) => (li as HTMLElement).dataset.slug));
    expect(order).toEqual(shown(items, state({}, '', 'title')));
    expect(order).not.toEqual(shown(items, state({})));
    expect(new URL(page.url()).search).toBe('?sort=title');
  });

  test('the view sorts, when the build has views', async ({ page }) => {
    await page.goto('/?sort=popular');
    const popular = page.locator('#facets input[name=sort][value=popular]');
    test.skip((await popular.count()) === 0, 'no stats/views/ in this build');
    const items = await catalog(page);
    const order = () =>
      page
        .locator('.grid > li')
        .evaluateAll((lis) => lis.map((li) => (li as HTMLElement).dataset.slug));
    await expect(popular).toBeChecked();
    expect(await order()).toEqual(shown(items, state({}, '', 'popular')));
    await page.locator('#facets input[name=sort][value=views]').check({ force: true });
    expect(await order()).toEqual(shown(items, state({}, '', 'views')));
    expect(new URL(page.url()).search).toBe('?sort=views');
  });

  test('a filtered load fills the count before it becomes the live region', async ({ page }) => {
    await page.addInitScript(() => {
      const seen: string[] = [];
      (window as unknown as { seen: string[] }).seen = seen;
      new MutationObserver((records) => {
        for (const r of records) {
          const el = r.target instanceof Element ? r.target : r.target.parentElement;
          if (el?.id === 'result-count')
            seen.push(r.type === 'attributes' ? `role was ${r.oldValue ?? 'unset'}` : 'text');
        }
      }).observe(document, {
        subtree: true,
        childList: true,
        characterData: true,
        attributes: true,
        attributeFilter: ['role'],
        attributeOldValue: true,
      });
    });
    await page.goto('/?technique=drafting');
    const items = await catalog(page);
    await expect(page.locator('#result-count')).toHaveAttribute('role', 'status');
    await expect(page.locator('#result-count')).toHaveText(
      results(shown(items, state({ technique: ['drafting'] })).length, items.length),
    );
    // The server's "N wallpapers", then the client's "n of N wallpapers", and only then the role.
    expect(await page.evaluate(() => (window as unknown as { seen: string[] }).seen)).toEqual([
      'text',
      'text',
      'role was unset',
    ]);
  });

  test('the query string restores the filter and ignores unknown values', async ({ page }) => {
    await page.goto('/?technique=instrument&technique=nonsense&sort=title&q=radar');
    const items = await catalog(page);
    await expect(box(page, 'technique', 'instrument')).toBeChecked();
    await expect(page.locator('#q')).toHaveValue('radar');
    await expect(page.locator('#facets input[name=sort][value=title]')).toBeChecked();
    const want = shown(items, state({ technique: ['instrument'] }, 'radar', 'title'));
    expect(want).toContain('radar-sweep');
    await expect(page.locator('#result-count')).toHaveText(results(want.length, items.length));
    expect(await visibleSlugs(page)).toEqual(want);
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
  test('a plate whose recolor fails to load shows the template, then recolors on a retry', async ({
    page,
  }) => {
    await page.addInitScript(() => localStorage.setItem('walldye.theme', 'nord'));
    let failures = 0;
    await page.route('**/*.slots.json', (route) =>
      failures++ < 3 ? route.fulfill({ status: 503, body: '' }) : route.continue(),
    );
    await page.goto('/');
    const srcs = () =>
      page
        .locator('.grid .plate > img')
        .evaluateAll((imgs) => imgs.map((i) => i.getAttribute('src') ?? ''));
    // The untouched template stands in, with the alt text, until the retry.
    await expect.poll(async () => (await srcs()).some((s) => s.startsWith('/t/'))).toBe(true);
    await expect(page.locator('.grid .plate > img[src^="/t/"]').first()).toHaveAttribute(
      'alt',
      /./,
    );
    expect(failures).toBeGreaterThanOrEqual(3);
    await expect
      .poll(async () => (await srcs()).every((s) => s.startsWith('blob:')), { timeout: 10_000 })
      .toBe(true);
  });

  test('every plate gets an image with the description as alt text', async ({ page }) => {
    await page.goto('/');
    // Plates load as they come near the view.
    await page.locator('.grid > li[data-slug=schotter]').scrollIntoViewIfNeeded();
    const img = page.locator('.grid > li[data-slug=schotter] .plate > img');
    await expect(img).toHaveAttribute('alt', /^Twenty-nine columns/);
    await expect(img).toHaveAttribute('width', '1920');
  });
});
