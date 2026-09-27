/**
 * docs/design.md, Tests: with about 24 plates of the 20 heaviest current SVGs in view and the CPU
 * slowed 4×, a theme change makes no main-thread task longer than 200 ms. Chromium only (CPU
 * throttling and long-task timing); the `perf` project runs it after the other projects so no other
 * test competes for the CPU.
 *
 * The SVGs are the nixos backgrounds until M2 imports them into the catalogue; point
 * WALLDYE_PERF_SVGS at another folder to use different files. They are never copied into the site:
 * the test serves the built index with its grid swapped for the fixture plates, and the templates
 * and slots from memory. Each slot gets coefficients that keep its fireproof colour under fireproof
 * and move with the seeds otherwise, so every theme change recolours every plate.
 */
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';
import { hexToRgb, PRESETS } from '../../src/lib/theme';
import { findColours } from '../../src/lib/tokenize';

const DIR = process.env.WALLDYE_PERF_SVGS ?? join(homedir(), 'nixos/modules/desktop/dms/backgrounds');
const HEAVIEST = 20;
const PLATES = 24;
const THROTTLE = 4;
const BUDGET_MS = 200;
/** Theme changes, in order: dark to dark, dark to light (every fixture is dark-only, so bg and fg swap) and back to dark. */
const CHANGES = ['nord', 'flexoki-light', 'gruvbox-dark'];

interface Fixture {
  name: string;
  bytes: number;
  svgUrl: string;
  slotsUrl: string;
  svg: string;
  slots: string;
}

/** A slots.json for `svg`: one coefficient row per distinct colour, reproducing it exactly under fireproof. */
function syntheticSlots(svg: string, sha: string): string {
  const [bg, fg, accent] = [PRESETS.fireproof.bg, PRESETS.fireproof.fg, PRESETS.fireproof.accent].map(hexToRgb);
  const [a, b, c] = [0.5, 0.3, 0.2];
  const rows = new Map<string, number>();
  const coefs: number[][] = [];
  const occ = findColours(svg).map(([, , colour]) => {
    let i = rows.get(colour);
    if (i === undefined) {
      const rgb = hexToRgb(colour);
      i = coefs.push([a, b, c, ...[0, 1, 2].map((k) => rgb[k] - (a * bg[k] + b * fg[k] + c * accent[k]))]) - 1;
      rows.set(colour, i);
    }
    return i;
  });
  const entry = { file: '16x9.svg', sha256: sha, n: occ.length, coefs, occ };
  return JSON.stringify({ design_sha: '', focus: [0.5, 0.5], cells: [], probes: {}, checked: '', '16:9/dark': entry });
}

function fixtures(): Fixture[] {
  const files = readdirSync(DIR)
    .filter((f) => f.endsWith('.svg'))
    .map((f) => ({ f, bytes: statSync(join(DIR, f)).size }))
    .sort((x, y) => y.bytes - x.bytes)
    .slice(0, HEAVIEST);
  return files.map(({ f, bytes }) => {
    const svg = readFileSync(join(DIR, f), 'utf8');
    const sha = createHash('sha256').update(svg).digest('hex');
    return { name: f.replace(/\.svg$/, ''), bytes, svgUrl: `/perf/${sha.slice(0, 12)}.svg`, slotsUrl: `/perf/${sha.slice(0, 12)}.slots.json`, svg, slots: syntheticSlots(svg, sha) };
  });
}

const attr = (s: string) => s.replaceAll('&', '&amp;').replaceAll('"', '&quot;');

test.describe('theme change performance', () => {
  test.skip(({ browserName }) => browserName !== 'chromium', 'CPU throttling and long-task timing are Chromium-only');
  test.skip(!existsSync(DIR), `no SVGs at ${DIR} (set WALLDYE_PERF_SVGS)`);
  test.use({ viewport: { width: 1920, height: 2800 }, deviceScaleFactor: 1, colorScheme: 'dark' });
  test.setTimeout(240_000);

  test(`no task over ${BUDGET_MS} ms with ${PLATES} plates of the ${HEAVIEST} heaviest SVGs at ${THROTTLE}× slowdown`, async ({ page, context }) => {
    const fx = fixtures();
    expect(fx.length).toBe(HEAVIEST);
    const byUrl = new Map(fx.flatMap((f) => [[f.svgUrl, { body: f.svg, type: 'image/svg+xml' }], [f.slotsUrl, { body: f.slots, type: 'application/json' }]]));
    await page.route('**/perf/*', (route) => {
      const hit = byUrl.get(new URL(route.request().url()).pathname);
      return hit ? route.fulfill({ body: hit.body, contentType: hit.type }) : route.fulfill({ status: 404 });
    });
    await page.route(/\/$/, async (route) => {
      const res = await route.fetch();
      const html = await res.text();
      const li = html.match(/<li data-slug="radar-sweep".*?<\/li>/s)?.[0];
      expect(li, 'the index has no radar-sweep plate to copy').toBeTruthy();
      const plates = Array.from({ length: PLATES }, (_, i) => {
        const f = fx[i % fx.length];
        const slug = `perf-${i}`;
        return li!
          .replaceAll('radar-sweep', slug)
          .replace(/data-templates="[^"]*"/, `data-templates="${attr(JSON.stringify({ '16:9/dark': f.svgUrl }))}"`)
          .replace(/data-slots="[^"]*"/, `data-slots="${f.slotsUrl}"`)
          .replace(/<noscript>.*?<\/noscript>/s, '')
          .replace(/(<h2 class="t" id="t-[^"]+">)[^<]*/, `$1${f.name}`);
      });
      await route.fulfill({ response: res, body: html.replace(/(<ul class="grid">).*?(<\/ul>)/s, `$1${plates.join('')}$2`) });
    });

    await page.goto('/');
    const imgs = page.locator('.grid .plate > img');
    await expect(imgs).toHaveCount(PLATES, { timeout: 60_000 });
    const inView = await page.locator('.grid > li').evaluateAll((lis) => lis.filter((li) => li.getBoundingClientRect().bottom <= innerHeight).length);
    expect(inView, 'plates fully in view').toBeGreaterThanOrEqual(PLATES - 3);

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
      const before = await imgs.evaluateAll((els) => els.map((e) => (e as HTMLImageElement).src));
      const start = Date.now();
      await page.evaluate((p) => document.querySelector<HTMLButtonElement>(`#picker button[data-preset="${p}"]`)!.click(), preset);
      await expect
        .poll(
          () =>
            page.evaluate((old) => {
              const plates = [...document.querySelectorAll('.grid .plate')];
              return plates.every((p) => {
                const shown = p.querySelectorAll<HTMLImageElement>(':scope > img');
                return shown.length === 1 && shown[0].src.startsWith('blob:') && !old.includes(shown[0].src);
              });
            }, before),
          { timeout: 120_000, intervals: [250] },
        )
        .toBe(true);
      const settled = Date.now() - start;
      // Let a task still running at the last poll finish and report.
      await page.waitForTimeout(300);
      const long = await page.evaluate(() => (window as unknown as { __long: number[] }).__long.splice(0));
      const worst = Math.max(0, ...long);
      results.push(`${preset}: ${PLATES} plates in ${settled} ms, ${long.length} tasks over 50 ms, longest ${worst} ms`);
      expect(worst, `${preset}: tasks ${JSON.stringify(long)}`).toBeLessThanOrEqual(BUDGET_MS);
    }
    const total = fx.reduce((n, f) => n + f.bytes, 0);
    test.info().annotations.push({ type: 'perf', description: `${HEAVIEST} SVGs, ${(total / 1e6).toFixed(1)} MB; slowdown ${(slow / fast).toFixed(1)}×; ${results.join('; ')}` });
  });
});
