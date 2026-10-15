/**
 * Smoke test of a running server: loads the index and a detail page in Chromium, Firefox and WebKit
 * under a non-default theme, waits for the plates, saves screenshots and reports console errors,
 * how many plates drew, and whether a live theme change repaints a plate without a fetch.
 *
 * Usage: scripts/with-browsers.sh pnpm exec tsx scripts/check/render.ts <baseUrl> [outDir]
 */
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium, firefox, webkit } from '@playwright/test';

const base = process.argv[2] ?? 'http://localhost:3000';
const out = resolve(process.argv[3] ?? join(process.env.CLAUDE_JOB_DIR ?? '.', 'tmp', 'render'));
mkdirSync(out, { recursive: true });
const report: Record<string, unknown> = {};

for (const type of [chromium, firefox, webkit]) {
  const browser = await type.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning')
      errors.push(`${m.type()}: ${m.text().slice(0, 200)}`);
  });
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message.slice(0, 200)}`));
  const r: Record<string, unknown> = {};
  await page.goto(`${base}/?t=nord`, { waitUntil: 'networkidle' });
  r.indexUses = await page.locator('.grid .plate use').count();
  r.htmlRegime = await page.evaluate(() => document.documentElement.dataset.regime);
  r.addressAfterBoot = new URL(page.url()).search;
  await page.screenshot({ path: join(out, `${type.name()}-index.png`) });
  await page.goto(`${base}/tartan`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  r.detailInlineDefs = await page.locator('.spread .plate defs').count();
  await page.screenshot({ path: join(out, `${type.name()}-tartan-nord.png`) });
  const fetched: string[] = [];
  page.on('request', (q) => fetched.push(q.url()));
  await page.evaluate(() => {
    for (const [k, v] of Object.entries({
      '--bg-r': '250',
      '--bg-g': '244',
      '--bg-b': '237',
      '--fg-r': '87',
      '--fg-g': '82',
      '--fg-b': '121',
      '--ac-r': '180',
      '--ac-g': '99',
      '--ac-b': '122',
      '--dk': '0',
      '--lt': '1',
    }))
      document.documentElement.style.setProperty(k, v);
  });
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(out, `${type.name()}-tartan-live-light.png`) });
  r.fetchesOnThemeChange = fetched.length;
  await page.goto(`${base}/dither-moon`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  r.moonUses = await page.locator('.spread .plate use').count();
  await page.screenshot({ path: join(out, `${type.name()}-moon.png`) });
  r.errors = errors;
  report[type.name()] = r;
  await browser.close();
}
console.log(JSON.stringify(report, null, 1));
