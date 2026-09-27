import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];
const THEMES = ['fireproof', 'flexoki-light', 'nord'] as const;

/**
 * Violations accepted on purpose, by rule and the selector of every node it flags.
 * The footnote back link is a lone "↑" after the sentence (SPEC 6.8), so its glyph, not its colour,
 * sets it apart from the text; axe cannot tell a symbol from a word.
 */
const ACCEPTED: Record<string, string> = { 'link-in-text-block': '.back' };

/** Pages and states the sweep visits; `width` limits a state to one viewport width. */
const STATES: { name: string; path: string; width?: number; act?: (page: Page) => Promise<void> }[] = [
  { name: 'index', path: '/' },
  { name: 'index filtered', path: '/?technique=drafting&q=s' },
  { name: 'index with nothing found', path: '/?q=zebra' },
  { name: 'index with the phone filter open', path: '/?other=any-screen', width: 390, act: (page) => page.click('.filter > summary') },
  { name: 'shared theme', path: '/about?t=gruvbox-dark' },
  { name: 'picker with both messages', path: '/', act: pickerMessages },
  { name: 'schotter', path: '/schotter' },
  { name: 'schotter at a footnote', path: '/schotter#fn1' },
  { name: 'dither-moon cropped', path: '/dither-moon?shape=16x10' },
  { name: 'radar-sweep cropped', path: '/radar-sweep?shape=21x9&crop=0.2' },
  { name: 'about', path: '/about' },
  { name: 'not found', path: '/no-such-wallpaper' },
];

async function pickerMessages(page: Page): Promise<void> {
  await page.click('#theme-button');
  await page.locator('#seed-fg').fill('#232221');
  await expect(page.locator('#faint-msg')).toBeVisible();
  await page.locator('#seed-accent').fill('#CF6A4');
  await page.locator('#seed-bg').focus();
  await expect(page.locator('#seed-msg')).toBeVisible();
}

/**
 * [selector, ratio, required] for each selector: its text colour (with opacity) against the first
 * opaque background behind it, 3:1 for text of 24px and up, 4.5:1 otherwise.
 */
async function measureContrast(page: Page, selectors: string[]): Promise<[string, number, number][]> {
  return page.evaluate((sels) => {
    const rgba = (c: string) => {
      const m = c.match(/[\d.]+/g)!.map(Number);
      return [m[0], m[1], m[2], m[3] ?? 1];
    };
    const lin = (v: number) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    const lum = ([r, g, b]: number[]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    return sels.map((sel) => {
      const el = document.querySelector(sel)!;
      let bg = [255, 255, 255, 1];
      for (let p: Element | null = el; p; p = p.parentElement) {
        const c = rgba(getComputedStyle(p).backgroundColor);
        if (c[3] === 1) {
          bg = c;
          break;
        }
      }
      let alpha = rgba(getComputedStyle(el).color)[3];
      for (let p: Element | null = el; p; p = p.parentElement) alpha *= Number(getComputedStyle(p).opacity);
      const fg = rgba(getComputedStyle(el).color).slice(0, 3).map((v, i) => v * alpha + bg[i] * (1 - alpha));
      const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
      return [sel, (a + 0.05) / (b + 0.05), parseFloat(getComputedStyle(el).fontSize) >= 24 ? 3 : 4.5] as [string, number, number];
    });
  }, selectors);
}

/** axe violations not in ACCEPTED, as readable lines. */
function unexpected(violations: Awaited<ReturnType<AxeBuilder['analyze']>>['violations']): string[] {
  return violations.flatMap((v) =>
    v.nodes
      .filter((n) => !(ACCEPTED[v.id] && n.target.join(' ').endsWith(ACCEPTED[v.id])))
      .map((n) => `${v.id} (${v.impact}) ${n.target.join(' ')}: ${n.failureSummary?.replace(/\s+/g, ' ')}`),
  );
}

test.describe('axe', () => {
  for (const theme of THEMES) {
    for (const width of [1440, 390]) {
      test(`${theme} at ${width}px`, async ({ page, browserName }) => {
        test.skip(browserName !== 'chromium' && (theme !== 'fireproof' || width !== 1440), 'axe reads the DOM and computed styles, which the engines agree on: the full sweep runs on Chromium');
        test.setTimeout(120_000);
        await page.setViewportSize({ width, height: width < 500 ? 844 : 1000 });
        // Saved as the visitor's own theme; `?t=` in a state still shows a shared one on top.
        await page.addInitScript((t) => {
          if (!sessionStorage.getItem('walldye.axe')) localStorage.setItem('walldye.theme', t);
          sessionStorage.setItem('walldye.axe', '1');
        }, theme);
        const found: string[] = [];
        for (const s of STATES) {
          if (s.width && s.width !== width) continue;
          await page.goto(s.path);
          await page.evaluate(() => document.fonts.ready);
          await s.act?.(page);
          const all = await new AxeBuilder({ page }).withTags(TAGS).analyze();
          found.push(...unexpected(all.violations).map((l) => `${s.name}: ${l}`));
          // The hairline rules are 1px background gradients, which axe cannot see past. They sit under
          // no text, so drop them and measure every text node against the plain page colour.
          await page.addStyleTag({ content: '*, *::before, *::after { background-image: none !important; }' });
          const contrast = await new AxeBuilder({ page }).withRules(['color-contrast', 'color-contrast-enhanced', 'link-in-text-block']).analyze();
          found.push(...unexpected(contrast.violations.filter((v) => v.id !== 'color-contrast-enhanced')).map((l) => `${s.name} (no rules): ${l}`));
          // What axe leaves unmeasured (a lone symbol, wrapped lines that overlap) is measured here instead.
          const unsure = contrast.incomplete.filter((v) => v.id === 'color-contrast').flatMap((v) => v.nodes.map((n) => n.target.join(' ')));
          for (const [target, ratio, min] of await measureContrast(page, unsure)) {
            if (ratio < min) found.push(`${s.name}: ${target} contrast ${ratio.toFixed(2)} < ${min}`);
          }
        }
        expect(found).toEqual([]);
      });
    }
  }
});

test.describe('structure', () => {
  test.use({ viewport: { width: 1440, height: 1000 } });

  for (const path of ['/', '/schotter', '/about', '/no-such-wallpaper']) {
    test(`${path} has one banner, one main, named navs and a skip link`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole('banner')).toHaveCount(1);
      await expect(page.getByRole('main')).toHaveCount(1);
      await expect(page.locator('h1')).toHaveCount(1);
      for (const nav of await page.getByRole('navigation').all()) expect(await nav.getAttribute('aria-label')).toBeTruthy();
      await expect(page.getByRole('navigation', { name: 'Site' })).toBeVisible();
      await page.keyboard.press('Tab');
      await expect(page.locator('.skip')).toBeFocused();
      await expect(page.locator('.skip')).toBeInViewport();
      await page.keyboard.press('Enter');
      await expect(page).toHaveURL(/#main$/);
    });
  }

  test('the not-found page, served at every missing address, stays out of search results', async ({ page }) => {
    await page.goto('/no-such-wallpaper');
    await expect(page.locator('meta[name=robots]')).toHaveAttribute('content', 'noindex');
    await expect(page.locator('link[rel=canonical], meta[property="og:url"]')).toHaveCount(0);
    await page.goto('/schotter');
    await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', /\/schotter$/);
    await expect(page.locator('meta[name=robots]')).toHaveCount(0);
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
      // Plate links draw their ring on the plate (SPEC 5); segmented radios on the label text.
      const plate = el.querySelector('.plate');
      const ringOn = plate ? getComputedStyle(plate, '::after').boxShadow : '';
      const seg = el.matches('.seg input') ? getComputedStyle(el.nextElementSibling as Element).outlineStyle : 'none';
      const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) || /2px/.test(ringOn) || seg !== 'none';
      const labelledBy = el.getAttribute('aria-labelledby')?.split(/\s+/).map((id) => document.getElementById(id)?.innerText ?? '').join(' ');
      const label = (labelledBy || el.getAttribute('aria-label') || el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40);
      const what = `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el instanceof HTMLInputElement ? `[${el.name}=${el.value}]` : ''} ${label}`.trim();
      const shown = r.width > 0 && r.height > 0 && cs.visibility !== 'hidden';
      return { what, visible: shown, ring };
    });
    // Past the last stop focus goes to the browser, wraps to the first, or (Firefox) stays put.
    if (!stop || (stops.length && (stop.what === stops[0].what || stop.what === stops.at(-1)!.what))) break;
    stops.push(stop);
  }
  return stops;
}

test.describe('focus order', () => {
  test.use({ viewport: { width: 1440, height: 1000 }, colorScheme: 'dark' });

  test('the index runs header, filter, then plates, each stop visible with a ring', async ({ page }) => {
    await page.goto('/');
    const stops = await tabStops(page);
    const names = stops.map((s) => s.what);
    const at = (re: RegExp) => names.findIndex((n) => re.test(n));
    expect(names[0]).toMatch(/^a Skip to content/);
    expect(at(/^a Walldye/)).toBeLessThan(at(/^button#theme-button/));
    expect(at(/^button#theme-button/)).toBeLessThan(at(/^input#q/));
    expect(at(/^input#q/)).toBeLessThan(at(/^input\[sort=newest\]/));
    expect(at(/^input\[sort=newest\]/)).toBeLessThan(at(/^input\[technique=/));
    // One stop per radio group, then the plates in grid order.
    expect(names.filter((n) => n.startsWith('input[sort='))).toHaveLength(1);
    expect(names.filter((n) => /^a (One-bit moon|Radar sweep|Schotter)/.test(n))).toEqual(['a One-bit moon', 'a Radar sweep', 'a Schotter, sideways']);
    expect(at(/^a One-bit moon/)).toBeGreaterThan(at(/^input\[technique=/));
    for (const s of stops.slice(1)) {
      expect(s.visible, `${s.what} is off screen`).toBe(true);
      expect(s.ring, `${s.what} has no focus ring`).toBe(true);
    }
  });

  test('a detail page runs label, colours, export, notes, then the source code', async ({ page }) => {
    await page.goto('/schotter');
    const stops = await tabStops(page);
    const names = stops.map((s) => s.what);
    const at = (re: RegExp) => {
      const i = names.findIndex((n) => re.test(n));
      expect(i, `${re} is not a stop in ${JSON.stringify(names)}`).toBeGreaterThanOrEqual(0);
      return i;
    };
    // No neighbour links between the facts and the colours (docs/design.md, Detail).
    expect(names.filter((n) => /^a (← Index|Previous:|Next:)/.test(n))).toEqual([]);
    const order = [/^button#theme-button/, /^a#fnref1 Source 1/, /^a technical drawing/, /^button Change/, /^input\[fmt=png\]/, /^input\[asp=16:9\]/, /^input\[size=2560x1440\]/, /^button#download/, /^a Schotter$/, /^a Back to text/, /^button Copy$/, /^pre design\.py source/, /^pre Run command/];
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
