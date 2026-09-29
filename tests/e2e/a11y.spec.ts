import { expect, type Page, test } from '@playwright/test';

test.describe('structure', () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  for (const path of ['/', '/schotter', '/about', '/no-such-wallpaper']) {
    test(`${path} has one banner, one main, named navs and a skip link`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole('banner')).toHaveCount(1);
      await expect(page.getByRole('main')).toHaveCount(1);
      await expect(page.locator('h1')).toHaveCount(1);
      for (const nav of await page.getByRole('navigation').all())
        expect(await nav.getAttribute('aria-label')).toBeTruthy();
      await expect(page.getByRole('navigation', { name: 'Site' })).toBeVisible();
      await page.keyboard.press('Tab');
      await expect(page.locator('.skip')).toBeFocused();
      await expect(page.locator('.skip')).toBeInViewport();
      await page.keyboard.press('Enter');
      await expect(page).toHaveURL(/#main$/);
    });
  }

  test('the not-found page, served at every missing address, stays out of search results', async ({
    page,
  }) => {
    await page.goto('/no-such-wallpaper');
    await expect(page.locator('meta[name=robots]')).toHaveAttribute('content', 'noindex');
    await expect(page.locator('link[rel=canonical], meta[property="og:url"]')).toHaveCount(0);
    await page.goto('/schotter');
    await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', /\/schotter$/);
    await expect(page.locator('meta[name=robots]')).toHaveCount(0);
  });

  test('robots.txt lets every crawler in and names the sitemap', async ({ request }) => {
    const robots = await request.get('/robots.txt');
    expect(robots.status()).toBe(200);
    expect(await robots.text()).toBe(
      'User-agent: *\nAllow: /\n\nSitemap: https://walldye.com/sitemap-index.xml\n',
    );
  });
});

interface Stop {
  what: string;
  visible: boolean;
  ring: boolean;
}

/** Tabs from the top of the page until focus leaves it or comes round again, describing each stop. */
async function tabStops(page: Page, limit = 80): Promise<Stop[]> {
  const stops: Stop[] = [];
  await page.locator('body').focus();
  for (let i = 0; i < limit; i++) {
    await page.keyboard.press('Tab');
    const stop = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      // Plate links draw their ring on the plate; segmented radios on the label text.
      const plate = el.querySelector('.plate');
      const ringOn = plate ? getComputedStyle(plate, '::after').boxShadow : '';
      const seg = el.matches('.seg input')
        ? getComputedStyle(el.nextElementSibling as Element).outlineStyle
        : 'none';
      const ring =
        (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) ||
        /2px/.test(ringOn) ||
        seg !== 'none';
      const labelledBy = el
        .getAttribute('aria-labelledby')
        ?.split(/\s+/)
        .map((id) => document.getElementById(id)?.innerText ?? '')
        .join(' ');
      const label = (labelledBy || el.getAttribute('aria-label') || el.innerText || '')
        .trim()
        .replace(/\s+/g, ' ')
        .slice(0, 40);
      const what =
        `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el instanceof HTMLInputElement ? `[${el.name}=${el.value}]` : ''} ${label}`.trim();
      const shown = r.width > 0 && r.height > 0 && cs.visibility !== 'hidden';
      return { what, visible: shown, ring };
    });
    // Past the last stop focus goes to the browser, wraps to the first, or (Firefox) stays put.
    if (
      !stop ||
      (stops.length && (stop.what === stops[0].what || stop.what === stops.at(-1)!.what))
    )
      break;
    stops.push(stop);
  }
  return stops;
}

test.describe('focus order', () => {
  test.use({ viewport: { width: 1440, height: 1000 }, colorScheme: 'dark' });

  test('the index runs header, filter, then plates, each stop visible with a ring', async ({
    page,
  }) => {
    await page.goto('/');
    const stops = await tabStops(page);
    const names = stops.map((s) => s.what);
    const at = (re: RegExp) => names.findIndex((n) => re.test(n));
    expect(names[0]).toMatch(/^a Skip to content/);
    expect(at(/^a Walldye/)).toBeLessThan(at(/^button#theme-button/));
    expect(at(/^button#theme-button/)).toBeLessThan(at(/^input#q/));
    expect(at(/^input#q/)).toBeLessThan(at(/^input\[sort=newest\]/));
    expect(at(/^input\[sort=newest\]/)).toBeLessThan(at(/^input\[technique=/));
    // One stop per radio group, then the plates in grid order (as far as the walk goes).
    expect(names.filter((n) => n.startsWith('input[sort='))).toHaveLength(1);
    const titles = await page
      .locator('.grid > li')
      .evaluateAll((lis) => lis.map((li) => `a ${(li as HTMLElement).dataset.title}`.slice(0, 42)));
    const firstPlate = names.indexOf(titles[0]);
    expect(firstPlate).toBeGreaterThan(at(/^input\[(technique|subject|lineage|other)=/));
    const plates = names.slice(firstPlate);
    expect(plates.length).toBeGreaterThanOrEqual(5);
    expect(plates).toEqual(titles.slice(0, plates.length));
    for (const s of stops.slice(1)) {
      expect(s.visible, `${s.what} is off screen`).toBe(true);
      expect(s.ring, `${s.what} has no focus ring`).toBe(true);
    }
  });

  test('a detail page runs label, colours, export, notes, then the source code', async ({
    page,
  }) => {
    await page.goto('/schotter');
    const stops = await tabStops(page);
    const names = stops.map((s) => s.what);
    const at = (re: RegExp) => {
      const i = names.findIndex((n) => re.test(n));
      expect(i, `${re} is not a stop in ${JSON.stringify(names)}`).toBeGreaterThanOrEqual(0);
      return i;
    };
    // No neighbour links between the facts and the colours.
    expect(names.filter((n) => /^a (← Index|Previous:|Next:)/.test(n))).toEqual([]);
    const order = [
      /^button#theme-button/,
      /^a#fnref1 Source 1/,
      /^a technical drawing/,
      /^button Change/,
      /^input\[fmt=png\]/,
      /^input\[asp=16:9\]/,
      /^input\[size=2560x1440\]/,
      /^button#download/,
      /^a Schotter$/,
      /^a Back to text/,
      /^button Copy$/,
      /^pre design\.py source/,
      /^pre Run command/,
    ];
    const idx = order.map(at);
    expect(idx).toEqual([...idx].sort((a, b) => a - b));
    for (const s of stops.slice(1)) expect(s.ring, `${s.what} has no focus ring`).toBe(true);
  });

  test('the picker takes focus after its button and gives it back on Escape', async ({ page }) => {
    await page.goto('/about');
    await page.locator('#theme-button').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('#picker')).toBeVisible();
    await expect(page.locator('#theme-button')).toHaveAttribute('aria-expanded', 'true');
    await page.keyboard.press('Tab');
    await expect(page.locator('#picker button[data-preset=fireproof]')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.locator('#picker')).toBeHidden();
    await expect(page.locator('#theme-button')).toBeFocused();
    await expect(page.locator('#theme-button')).toHaveAttribute('aria-expanded', 'false');
  });
});
