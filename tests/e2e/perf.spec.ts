/**
 * On the built index with the heaviest published templates in view and the CPU throttled, a theme
 * change makes no main-thread task longer than BUDGET_MS. Chromium only (CPU throttling and long-task
 * timing); the `perf` project runs it after the others so nothing competes for the CPU.
 */
import { readFileSync, statSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { ROOT } from './helpers';

const HEAVIEST = 20;
const PLATES = 24;
const THROTTLE = 4;
const BUDGET_MS = 200;
/** Theme changes, in order: dark to dark, dark to light and back to dark. */
const CHANGES = ['nord', 'flexoki-light', 'gruvbox-dark'];

/** The published pieces whose default 16:9 template is heaviest, heaviest first, with its size. */
function heaviest(): { slug: string; bytes: number }[] {
  const index = JSON.parse(readFileSync(`${ROOT}wallpapers/index.json`, 'utf8')) as Record<string, { draft: boolean }>;
  return Object.entries(index)
    .filter(([, v]) => !v.draft)
    .map(([slug]) => ({ slug, bytes: statSync(`${ROOT}wallpapers/${slug}/build/16x9.svg`).size }))
    .sort((a, b) => b.bytes - a.bytes || (a.slug < b.slug ? -1 : 1))
    .slice(0, HEAVIEST);
}

test.describe('theme change performance', () => {
  test.skip(({ browserName }) => browserName !== 'chromium', 'CPU throttling and long-task timing are Chromium-only');
  test.use({ viewport: { width: 1920, height: 2800 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  test.setTimeout(300_000);

  test(`no task over ${BUDGET_MS} ms with the ${HEAVIEST} heaviest templates among ${PLATES} plates in view at ${THROTTLE}× slowdown`, async ({ page, context }) => {
    const heavy = heaviest();
    expect(heavy.length).toBe(HEAVIEST);
    const first = heavy.map((h) => h.slug);
    // The index sorts newest first, so dating the heaviest plates later puts them at the top.
    await page.route(/\/$/, async (route) => {
      const res = await route.fetch();
      let html = await res.text();
      for (const slug of first) {
        const before = html;
        html = html.replace(new RegExp(`(<li data-slug="${slug}" data-title="[^"]*" data-added=")[^"]*"`), '$12100-01-01"');
        expect(html, `the index has no plate for ${slug}`).not.toBe(before);
      }
      await route.fulfill({ response: res, body: html });
    });

    await page.goto('/');
    const total = await page.locator('.grid > li').count();
    const inView = await page
      .locator('.grid > li')
      .evaluateAll((lis) => lis.filter((li) => li.getBoundingClientRect().bottom <= innerHeight).map((li) => (li as HTMLElement).dataset.slug!));
    expect(inView.length, 'plates fully in view').toBeGreaterThanOrEqual(PLATES - 3);
    expect(inView.slice(0, HEAVIEST).sort()).toEqual([...first].sort());

    /** src of each plate the index keeps current (within a viewport of the view), or null while it has no single loaded image. */
    const nearSrcs = () =>
      page.evaluate(() =>
        [...document.querySelectorAll<HTMLElement>('.grid > li')]
          .filter((li) => {
            const r = li.getBoundingClientRect();
            return r.bottom > -innerHeight && r.top < 2 * innerHeight;
          })
          .map((li) => {
            const imgs = li.querySelectorAll<HTMLImageElement>('.plate > img');
            return imgs.length === 1 && imgs[0].complete ? imgs[0].src : null;
          }),
      );
    await expect.poll(async () => (await nearSrcs()).every((s) => s !== null), { timeout: 120_000, intervals: [250] }).toBe(true);

    // A fixed workload, timed before and after, shows the slowdown took hold.
    const work = () =>
      page.evaluate(() => {
        const t0 = performance.now();
        let x = 0;
        for (let i = 0; i < 2e7; i++) x = (x + i * 7) % 1000003;
        return performance.now() - t0 + x * 0;
      });
    const fast = Math.min(await work(), await work());
    const cdp = await context.newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: THROTTLE });
    const slow = Math.min(await work(), await work());
    expect(slow / fast, `workload ${fast.toFixed(0)} ms, throttled ${slow.toFixed(0)} ms`).toBeGreaterThan(THROTTLE / 2);
    await page.evaluate(() => {
      const w = window as unknown as { __long: number[] };
      w.__long = [];
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) w.__long.push(Math.round(e.duration));
      }).observe({ type: 'longtask' });
    });

    const results: string[] = [];
    for (const preset of CHANGES) {
      const before = await nearSrcs();
      const start = Date.now();
      await page.evaluate((p) => document.querySelector<HTMLButtonElement>(`#picker button[data-preset="${p}"]`)!.click(), preset);
      await expect
        .poll(async () => (await nearSrcs()).every((s) => s !== null && s.startsWith('blob:') && !before.includes(s)), { timeout: 180_000, intervals: [250] })
        .toBe(true);
      const settled = Date.now() - start;
      // Let a task still running at the last poll finish and report.
      await page.waitForTimeout(300);
      const long = await page.evaluate(() => (window as unknown as { __long: number[] }).__long.splice(0));
      const worst = Math.max(0, ...long);
      results.push(`${preset}: ${before.length} plates in ${settled} ms, ${long.length} tasks over 50 ms, longest ${worst} ms`);
      expect(worst, `${preset}: tasks ${JSON.stringify(long)}`).toBeLessThanOrEqual(BUDGET_MS);
    }
    const bytes = heavy.reduce((n, h) => n + h.bytes, 0);
    test.info().annotations.push({
      type: 'perf',
      description: `${total} plates, ${inView.length} in view; ${HEAVIEST} heaviest templates, ${(bytes / 1e6).toFixed(1)} MB; slowdown ${(slow / fast).toFixed(1)}×; ${results.join('; ')}`,
    });
  });
});
