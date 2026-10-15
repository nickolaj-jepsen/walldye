/**
 * End-to-end smoke test of a running server in Chromium, Firefox and WebKit: the index filters,
 * theme changes, the detail page's versions, shapes, crop and motif (mouse, and pinch on a phone),
 * export downloads, the grid-to-page view transition, the social card, about, 404 and the code view.
 * Prints one line per check and a JSON summary; exits non-zero when any check fails.
 *
 * Usage: scripts/with-browsers.sh pnpm exec tsx scripts/check/smoke.ts <baseUrl> [outDir] [engines]
 */
import { mkdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  type Browser,
  type BrowserContext,
  type BrowserType,
  chromium,
  firefox,
  type Page,
  webkit,
} from '@playwright/test';
import { PNG } from 'pngjs';

const base = process.argv[2] ?? 'http://localhost:3000';
const out = resolve(process.argv[3] ?? join(process.env.CLAUDE_JOB_DIR ?? '.', 'tmp', 'smoke'));
const only = process.argv[4]?.split(',');
mkdirSync(out, { recursive: true });

interface CatalogPiece {
  slug: string;
  plates: Record<string, { dark: string; light: string }>;
  versions: { plates: Record<string, { dark: string; light: string }> }[];
}
const catalog = JSON.parse(readFileSync('src/generated/catalog.json', 'utf8')) as {
  pieces: CatalogPiece[];
};

type Result = { engine: string; check: string; ok: boolean; info?: string };
const results: Result[] = [];

function record(engine: string, check: string, ok: boolean, info?: unknown) {
  const text =
    info === undefined ? undefined : typeof info === 'string' ? info : JSON.stringify(info);
  results.push({ engine, check, ok, info: text });
  console.log(
    `${ok ? 'PASS' : 'FAIL'} ${engine.padEnd(8)} ${check}${text ? `  ${text.slice(0, 300)}` : ''}`,
  );
}

async function check(engine: string, name: string, fn: () => Promise<unknown>) {
  try {
    const r = await fn();
    if (r === false) record(engine, name, false);
    else record(engine, name, true, r === true || r === undefined ? undefined : r);
  } catch (e) {
    record(engine, name, false, (e as Error).message.split('\n').slice(0, 4).join(' | '));
  }
}

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg);
}

/** Distinct colors in a screenshot, coarsely bucketed. */
function colorsIn(buf: Buffer): number {
  const png = PNG.sync.read(buf);
  const seen = new Set<number>();
  for (let i = 0; i < png.data.length; i += 4 * 7) {
    seen.add(((png.data[i] >> 3) << 10) | ((png.data[i + 1] >> 3) << 5) | (png.data[i + 2] >> 3));
  }
  return seen.size;
}

function differs(a: Buffer, b: Buffer): number {
  const pa = PNG.sync.read(a);
  const pb = PNG.sync.read(b);
  if (pa.width !== pb.width || pa.height !== pb.height) return 1;
  let n = 0;
  for (let i = 0; i < pa.data.length; i += 4) {
    if (Math.abs(pa.data[i] - pb.data[i]) + Math.abs(pa.data[i + 1] - pb.data[i + 1]) > 24) n++;
  }
  return n / (pa.width * pa.height);
}

function watch(page: Page, errors: string[]) {
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`${m.text().slice(0, 240)}`);
  });
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message.slice(0, 240)}`));
}

/** Sets an input's value as a person would, past React's value tracking, and fires `input`. */
async function setValue(page: Page, selector: string, value: string) {
  await page
    .locator(selector)
    .first()
    .evaluate((el, v) => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
      set?.call(el, v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, value);
}

/** Scrolls `el` to the middle of the view; Playwright's own scrolling misses in WebKit here. */
async function reveal(el: ReturnType<Page['locator']>) {
  await el.evaluate((e) => e.scrollIntoView({ block: 'center' }));
  await el.page().waitForTimeout(200);
}

/** A screenshot of `el`'s box from the page, which never waits on a pending navigation. */
async function shotOf(el: ReturnType<Page['locator']>): Promise<Buffer> {
  const box = await el.boundingBox();
  if (!box) throw new Error('no box to shoot');
  return el.page().screenshot({ clip: box });
}

const params = (page: Page) => new URL(page.url()).searchParams;

async function settle(page: Page, ms = 400) {
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.waitForTimeout(ms);
}

async function indexFlows(engine: string, ctx: BrowserContext) {
  const page = await ctx.newPage();
  const errors: string[] = [];
  watch(page, errors);
  await page.goto(`${base}/`, { waitUntil: 'networkidle' });
  await settle(page);

  await check(engine, 'index: 194 entries, plates drawn', async () => {
    const n = await page.locator('.grid > li:not([hidden])').count();
    assert(n >= 194, `entries ${n}`);
    const first = page.locator('.grid > li .plate').first();
    const shot = await first.screenshot();
    const colors = colorsIn(shot);
    assert(colors > 3, `first plate has ${colors} colors`);
    await page.screenshot({ path: join(out, `${engine}-index.png`) });
    return `entries ${n}, first plate colors ${colors}`;
  });

  await check(engine, 'index: lazy plates draw on scroll', async () => {
    const last = page.locator('.grid > li .plate').nth(40);
    await reveal(last);
    await settle(page, 600);
    const uses = await last.locator('use').count();
    assert(uses > 0, 'no <use> after scroll');
    const colors = colorsIn(await last.screenshot());
    await page.evaluate(() => window.scrollTo(0, 0));
    return `colors ${colors}`;
  });

  await check(engine, 'index: facet box filters and writes the address (replace)', async () => {
    const before = await page.evaluate(() => history.length);
    const box = page.locator('input[name=technique][value=dither]');
    const expected = Number(await box.locator('xpath=..').locator('.count').textContent());
    await box.check({ force: true });
    await page.waitForFunction(() => location.search.includes('technique=dither'));
    await page.waitForTimeout(300);
    const n = await page.locator('.grid > li:not([hidden])').count();
    const line = await page.locator('#result-count').textContent();
    const after = await page.evaluate(() => history.length);
    assert(n === expected, `visible ${n}, count said ${expected}`);
    assert(after === before, `history grew ${before} -> ${after}`);
    return `${n} visible, "${line}"`;
  });

  await check(engine, 'index: search writes q and filters', async () => {
    await page.locator('#q').fill('moon');
    await page.waitForFunction(() => location.search.includes('q=moon'));
    await page.waitForTimeout(300);
    const n = await page.locator('.grid > li:not([hidden])').count();
    assert(n >= 1 && n < 25, `visible ${n}`);
    return `visible ${n}`;
  });

  await check(engine, 'index: clear keeps the shape, drops search and boxes', async () => {
    await page.locator('input[name=shape][value="21x9"]').check({ force: true });
    await page.waitForFunction(() => location.search.includes('shape=21x9'));
    await page.locator('button.clear').click();
    await page.waitForTimeout(300);
    const p = params(page);
    assert(!p.has('q') && !p.has('technique'), `left ${p}`);
    assert(p.get('shape') === '21x9', `shape ${p.get('shape')}`);
    const n = await page.locator('.grid > li:not([hidden])').count();
    assert(n >= 194, `visible ${n}`);
  });

  await check(engine, 'index: sort by title', async () => {
    await page.locator('input[name=sort][value=title]').check({ force: true });
    await page.waitForFunction(() => location.search.includes('sort=title'));
    await page.waitForTimeout(300);
    const titles = await page.locator('.grid > li:not([hidden]) .t').allTextContents();
    const sorted = [...titles].sort((a, b) => a.localeCompare(b));
    assert(titles.slice(0, 5).join() === sorted.slice(0, 5).join(), titles.slice(0, 5).join(', '));
    return titles.slice(0, 3).join(', ');
  });

  await check(engine, 'index: tall shape crops plates and links carry ?shape', async () => {
    await page.locator('input[name=shape][value="9x19.5"]').check({ force: true });
    await page.waitForFunction(() => location.search.includes('shape=9x19.5'));
    await settle(page);
    const shape = await page.locator('section.plates').getAttribute('data-shape');
    const href = await page.locator('.grid > li a').first().getAttribute('href');
    const box = await page.locator('.grid > li .plate').first().boundingBox();
    assert(shape === '9:19.5', `data-shape ${shape}`);
    assert(href?.includes('shape=9x19.5'), `href ${href}`);
    assert(box && box.height > box.width, `plate ${box?.width}x${box?.height}`);
    const colors = colorsIn(await page.locator('.grid > li .plate').first().screenshot());
    assert(colors > 2, `colors ${colors}`);
    await page.screenshot({ path: join(out, `${engine}-index-tall.png`) });
    return `href ${href}`;
  });

  await check(engine, 'index: a filtered address loads its state', async () => {
    await page.goto(`${base}/?subject=space&technique=line&q=moon&sort=title&shape=21x9`, {
      waitUntil: 'networkidle',
    });
    await settle(page);
    const s = await page.evaluate(() => ({
      q: (document.querySelector('#q') as HTMLInputElement).value,
      space: (document.querySelector('input[name=subject][value=space]') as HTMLInputElement)
        ?.checked,
      line: (document.querySelector('input[name=technique][value=line]') as HTMLInputElement)
        ?.checked,
      sort: (document.querySelector('input[name=sort]:checked') as HTMLInputElement)?.value,
      shape: (document.querySelector('input[name=shape]:checked') as HTMLInputElement)?.value,
      live: document.querySelector('#result-count')?.getAttribute('role'),
      line2: document.querySelector('#result-count')?.textContent,
    }));
    assert(
      s.q === 'moon' && s.space && s.line && s.sort === 'title' && s.shape === '21x9',
      JSON.stringify(s),
    );
    return s;
  });

  await check(engine, 'index: Colors row presses and applies a family', async () => {
    // A fresh context: in a second tab of the same one, Playwright never marks the router's prefetches
    // that the HTTP cache answers as finished on OpenNext, so network idle never comes.
    const fresh = await ctx.browser()?.newContext({
      viewport: { width: 1400, height: 900 },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
    });
    assert(fresh, 'no browser');
    const page = await fresh.newPage();
    watch(page, errors);
    await page.goto(`${base}/`, { waitUntil: 'networkidle' });
    await settle(page);
    const plate = page.locator('.grid > li .plate').first();
    const before = await shotOf(plate);
    const bg0 = await page.evaluate(() =>
      document.documentElement.style.getPropertyValue('--bg-r'),
    );
    const requests: string[] = [];
    const onReq = (r: { url(): string }) => requests.push(r.url());
    page.on('request', onReq);
    const buttons = page.locator('.themes button[aria-pressed]');
    const target = buttons.nth(3);
    const name = await target.getAttribute('aria-label');
    await target.click();
    await page.waitForTimeout(400);
    page.off('request', onReq);
    const pressed = await target.getAttribute('aria-pressed');
    const bg1 = await page.evaluate(() =>
      document.documentElement.style.getPropertyValue('--bg-r'),
    );
    const after = await shotOf(plate);
    const d = differs(before, after);
    assert(pressed === 'true', `pressed ${pressed}`);
    assert(bg0 !== bg1, `--bg-r stayed ${bg0}`);
    assert(d > 0.2, `plate changed ${(d * 100).toFixed(1)}%`);
    const t = requests.filter((u) => u.includes('/t/'));
    assert(t.length === 0, `fetched ${t.join(' ')}`);
    await fresh.close();
    return `${name}: --bg-r ${bg0} -> ${bg1}, plate ${(d * 100).toFixed(0)}% changed, ${requests.length} requests`;
  });

  record(engine, 'index: no console errors', errors.length === 0, errors.slice(0, 5));
  await page.close();
}

async function themeFlows(engine: string, ctx: BrowserContext) {
  const page = await ctx.newPage();
  const errors: string[] = [];
  watch(page, errors);
  const moon = catalog.pieces.find((p) => p.slug === 'dither-moon');
  assert(moon, 'no dither-moon');
  const refs = [moon.plates, ...moon.versions.map((v) => v.plates)].flatMap((p) =>
    Object.values(p),
  );
  const lightOnly = new Set(refs.filter((r) => r.dark !== r.light).map((r) => r.light));
  const darkOnly = new Set(refs.filter((r) => r.dark !== r.light).map((r) => r.dark));
  const fetched: string[] = [];
  page.on('request', (r) => {
    const m = /\/t\/([0-9a-f]+)\.svg/.exec(r.url());
    if (m) fetched.push(m[1]);
  });

  await page.goto(`${base}/dither-moon?t=nord`, { waitUntil: 'networkidle' });
  await settle(page, 600);

  await check(engine, 'theme: ?t= is taken and the shared line shows', async () => {
    const theme = await page.evaluate(() => document.documentElement.dataset.theme);
    const shared = await page.locator('#shared').isVisible();
    assert(theme === 'nord', `theme ${theme}`);
    assert(!page.url().includes('t=nord'), `address ${page.url()}`);
    assert(shared, 'shared line hidden');
  });

  await check(engine, 'theme: dark regime fetches no light-only template', async () => {
    const bad = fetched.filter((h) => lightOnly.has(h));
    assert(bad.length === 0, `fetched light ${bad.join()}`);
    const dark = fetched.filter((h) => darkOnly.has(h));
    assert(dark.length > 0, `no dark file fetched (${fetched.join()})`);
    return `fetched ${fetched.length} templates`;
  });

  await check(
    engine,
    'theme: picker preset to a light theme swaps to light templates',
    async () => {
      await page.locator('#shared button').first().click();
      await page.locator('#theme-button').click();
      await page.locator('#picker').waitFor({ state: 'visible' });
      fetched.length = 0;
      await page.locator('#picker [data-preset="flexoki-light"]').click();
      await settle(page, 600);
      const regime = await page.evaluate(() => document.documentElement.dataset.regime);
      const href = await page.locator('.spread .plate use').first().getAttribute('href');
      assert(regime === 'light', `regime ${regime}`);
      assert(
        [...lightOnly].some((h) => href?.includes(h)),
        `href ${href}`,
      );
      assert(
        fetched.some((h) => lightOnly.has(h)),
        `fetched ${fetched.join()}`,
      );
      await page.screenshot({ path: join(out, `${engine}-moon-light.png`) });
      return `href ${href}`;
    },
  );

  await check(engine, 'theme: dragging a color picker repaints the plate live', async () => {
    const plate = page.locator('.spread .plate');
    const before = await shotOf(plate);
    await setValue(page, '#picker input[type=color]', '#802020');
    await page.waitForTimeout(150);
    const bg = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--bg-r').trim(),
    );
    const after = await shotOf(plate);
    const d = differs(before, after);
    assert(bg === '128', `--bg-r ${bg}`);
    assert(d > 0.2, `plate changed ${(d * 100).toFixed(1)}%`);
    await page.waitForTimeout(500);
    const theme = await page.evaluate(() => document.documentElement.dataset.theme);
    return `--bg-r ${bg}, ${(d * 100).toFixed(0)}% changed, token ${theme}`;
  });

  await check(engine, 'theme: a family follows the scheme', async () => {
    await page.locator('#picker button.family').first().click();
    await page.waitForTimeout(300);
    const pressed = await page
      .locator('#picker button.family')
      .first()
      .getAttribute('aria-pressed');
    const theme = await page.evaluate(() => document.documentElement.dataset.theme);
    assert(pressed === 'true', `pressed ${pressed}`);
    await page.keyboard.press('Escape');
    return theme;
  });

  await check(engine, 'theme: favicon is themed', async () => {
    const icons = await page.evaluate(() =>
      [...document.querySelectorAll('link[rel~=icon]')].map((l) =>
        (l as HTMLLinkElement).href.slice(0, 40),
      ),
    );
    assert(icons.length === 2 && icons[1].startsWith('data:'), JSON.stringify(icons));
  });

  record(engine, 'theme: no console errors', errors.length === 0, errors.slice(0, 5));
  await page.close();
}

async function detailFlows(engine: string, ctx: BrowserContext) {
  const page = await ctx.newPage();
  const errors: string[] = [];
  watch(page, errors);
  await page.goto(`${base}/cassette`, { waitUntil: 'networkidle' });
  await settle(page, 600);

  await check(engine, 'detail: plate drawn', async () => {
    const colors = colorsIn(await page.locator('.spread .plate').screenshot());
    assert(colors > 2, `colors ${colors}`);
    await page.screenshot({ path: join(out, `${engine}-detail.png`) });
    return `colors ${colors}`;
  });

  await check(engine, 'detail: version switch writes ?v', async () => {
    const radios = page.locator('input[name=v]');
    const n = await radios.count();
    assert(n >= 2, `versions ${n}`);
    const value = await radios.nth(1).getAttribute('value');
    const alt0 = await page.locator('.spread .pic').getAttribute('aria-label');
    await radios.nth(1).check({ force: true });
    await page.waitForFunction((v) => location.search.includes(`v=${v}`), value);
    await settle(page);
    const alt1 = await page.locator('.spread .pic').getAttribute('aria-label');
    assert(alt0 !== alt1, 'alt text unchanged');
    return `v=${value}`;
  });

  await check(engine, 'detail: shape and crop write the address', async () => {
    await page.locator('input[name=asp][value="21:9"]').check({ force: true });
    await page.waitForFunction(() => location.search.includes('shape=21x9'));
    await page.locator('#crop').waitFor();
    await setValue(page, '#crop', '0.2');
    await page.waitForFunction(() => location.search.includes('crop='));
    return new URL(page.url()).search;
  });

  await check(engine, 'detail: crop window drags', async () => {
    await page.evaluate(() => window.scrollTo(0, 0));
    const win = page.locator('.spread .crop');
    const box = await win.boundingBox();
    assert(box, 'no crop window');
    const before = params(page).get('crop');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    // 21:9 crops along y.
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 + 40, { steps: 6 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const after = params(page).get('crop');
    assert(after !== before, `crop ${before} -> ${after}`);
    return `crop ${before} -> ${after}`;
  });

  await check(engine, 'detail: address round trip', async () => {
    const url = page.url();
    await page.goto(url, { waitUntil: 'networkidle' });
    await settle(page);
    const s = await page.evaluate(() => ({
      v: (document.querySelector('input[name=v]:checked') as HTMLInputElement)?.value,
      asp: (document.querySelector('input[name=asp]:checked') as HTMLInputElement)?.value,
      crop: (document.querySelector('#crop') as HTMLInputElement)?.value,
    }));
    const p = params(page);
    assert(s.v === p.get('v') && s.asp === '21:9', JSON.stringify(s));
    assert(
      Math.abs(Number(s.crop) - Number(p.get('crop'))) < 0.01,
      `crop ${s.crop} vs ${p.get('crop')}`,
    );
    return s;
  });

  await check(engine, 'detail: source code view and copy', async () => {
    await reveal(page.locator('details.appendix summary'));
    await page.locator('details.appendix summary').click();
    await page.locator('details.appendix .listing pre').waitFor();
    const lines = await page.locator('details.appendix .listing .line').count();
    const cmd = await page.locator('details.appendix .run pre').textContent();
    assert(lines > 10, `lines ${lines}`);
    assert(cmd?.includes('cassette'), `command ${cmd}`);
    if (engine === 'chromium') {
      await page.locator('[data-action=copy-source]').click();
      await page.waitForTimeout(200);
      const t = await page.locator('[data-action=copy-source]').textContent();
      assert(t?.includes('Copied'), `copy says ${t}`);
    }
    return `${lines} lines; ${cmd?.split('$').pop()?.trim().slice(0, 120)}`;
  });

  await check(engine, 'detail: lost script note', async () => {
    await page.goto(`${base}/arcs`, { waitUntil: 'networkidle' });
    await reveal(page.locator('details.appendix summary'));
    await page.locator('details.appendix summary').click();
    await page.getByText('The script for this wallpaper has been lost.').waitFor({ timeout: 3000 });
  });

  // Motif: mouse drag and corner resize on the inlined-defs piece.
  await page.goto(`${base}/impossible-triangle`, { waitUntil: 'networkidle' });
  await settle(page, 600);
  await check(engine, 'motif: handle drag writes ?at', async () => {
    const handle = page.locator('.motif-handle');
    const box = await handle.boundingBox();
    assert(box, 'no handle');
    const plate0 = await page.locator('.spread .plate').screenshot();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 - 90, box.y + box.height / 2 + 30, { steps: 8 });
    const mid = await page.evaluate(
      () => (document.querySelector('[data-motif-layer]') as SVGGElement | null)?.style.transform,
    );
    await page.mouse.up();
    await page.waitForFunction(() => location.search.includes('at='));
    await settle(page, 300);
    const plate1 = await page.locator('.spread .plate').screenshot();
    const d = differs(plate0, plate1);
    assert(d > 0.002, `plate changed ${(d * 100).toFixed(2)}%`);
    const box1 = await handle.boundingBox();
    assert(box1 && Math.abs(box1.x - (box.x - 90)) < 12, `handle at ${box1?.x} want ${box.x - 90}`);
    return `during drag transform "${mid}", ${new URL(page.url()).search}`;
  });

  await check(engine, 'motif: corner resize writes ?size', async () => {
    const handle = page.locator('.motif-handle');
    await handle.hover();
    const corner = page.locator('.motif-corner[data-corner="1,1"]');
    const box = await corner.boundingBox();
    assert(box, 'no corner');
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 50, box.y + box.height / 2 + 50, { steps: 6 });
    await page.mouse.up();
    await page.waitForFunction(() => location.search.includes('size='));
    return new URL(page.url()).search;
  });

  await check(engine, 'motif: ranges, Center and Reset', async () => {
    await reveal(page.locator('#place-x'));
    await setValue(page, '#place-x', '300');
    await page
      .waitForFunction(
        () => new URL(location.href).searchParams.get('at')?.startsWith('300'),
        undefined,
        { timeout: 3000 },
      )
      .catch(() => {});
    const at = params(page).get('at');
    assert(at?.startsWith('300'), `at ${at}`);
    await reveal(page.getByRole('button', { name: 'Center across' }));
    await page.getByRole('button', { name: 'Center across' }).click();
    await page.waitForTimeout(200);
    const at2 = params(page).get('at');
    await reveal(page.getByRole('button', { name: 'Reset' }));
    await page.getByRole('button', { name: 'Reset' }).click();
    await page.waitForTimeout(200);
    const p = params(page);
    assert(!p.has('at') && !p.has('size'), `left ${p}`);
    return `at ${at} -> ${at2}`;
  });

  await check(engine, 'export: SVG and PNG download', async () => {
    await page.goto(`${base}/impossible-triangle?shape=16x10&at=600,500`, {
      waitUntil: 'networkidle',
    });
    await settle(page, 600);
    const got: string[] = [];
    const formats = engine === 'chromium' ? ['svg', 'png', 'webp', 'jpeg'] : ['svg', 'png'];
    for (const fmt of formats) {
      const radio = page.locator(`input[name=fmt][value=${fmt}]`);
      if ((await radio.count()) === 0) throw new Error(`no ${fmt} radio`);
      await radio.check({ force: true });
      const wait = page.waitForEvent('download', { timeout: 60000 });
      await page.locator('#download').click();
      const dl = await wait;
      const path = await dl.path();
      const bytes = readFileSync(path);
      const head = bytes.subarray(0, 12);
      const kind =
        head.subarray(0, 4).toString('latin1') === '\x89PNG'
          ? 'png'
          : head.subarray(8, 12).toString('latin1') === 'WEBP'
            ? 'webp'
            : head[0] === 0xff && head[1] === 0xd8
              ? 'jpeg'
              : bytes.subarray(0, 200).toString('utf8').includes('<svg')
                ? 'svg'
                : 'unknown';
      assert(kind === fmt, `${fmt}: got ${kind} (${dl.suggestedFilename()})`);
      if (fmt === 'svg') {
        const svg = bytes.toString('utf8');
        assert(!svg.includes('var(--'), 'SVG still has var()');
      }
      got.push(`${dl.suggestedFilename()} ${bytes.length}B`);
    }
    return got.join('; ');
  });

  record(engine, 'detail: no console errors', errors.length === 0, errors.slice(0, 5));
  await page.close();
}

async function phoneFlows(engine: string, browser: Browser) {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    ...(engine === 'firefox' ? {} : { isMobile: true }),
    deviceScaleFactor: 1,
  });
  const page = await ctx.newPage();
  const errors: string[] = [];
  watch(page, errors);
  await page.goto(`${base}/impossible-triangle`, { waitUntil: 'networkidle' });
  await settle(page, 600);

  await check(engine, 'phone: tall shape and motif rows under the plate', async () => {
    const asp = await page.locator('.spread').getAttribute('data-aspect');
    const rows = await page.locator('.motif-near #motif-rows').count();
    const box = await page.locator('.spread .plate').boundingBox();
    await page.screenshot({ path: join(out, `${engine}-phone-detail.png`) });
    assert(rows === 1, `motif rows under plate: ${rows}`);
    return `aspect ${asp}, plate ${box?.width}x${box?.height}`;
  });

  await check(engine, 'phone: two-finger pinch writes ?size', async () => {
    const box = await page.locator('.spread .plate').boundingBox();
    assert(box, 'no plate');
    const cx = box.x + box.width / 2;
    const cy = box.y + box.height / 2;
    // A string, so tsx's __name helper never reaches the page.
    await page.evaluate(`(() => {
      const [cx, cy] = [${cx}, ${cy}];
      const el = document.elementFromPoint(cx, cy);
      function fire(type, id, x, y) {
        el.dispatchEvent(new PointerEvent(type, {
          pointerId: id, pointerType: 'touch', clientX: x, clientY: y, bubbles: true,
          cancelable: true, isPrimary: id === 1, button: type === 'pointermove' ? -1 : 0,
          buttons: type === 'pointerup' ? 0 : 1,
        }));
      }
      fire('pointerdown', 1, cx - 20, cy);
      fire('pointerdown', 2, cx + 20, cy);
      for (let i = 1; i <= 5; i++) {
        fire('pointermove', 1, cx - 20 - i * 12, cy);
        fire('pointermove', 2, cx + 20 + i * 12, cy);
      }
      fire('pointerup', 1, cx - 80, cy);
      fire('pointerup', 2, cx + 80, cy);
    })()`);
    await page.waitForFunction(() => location.search.includes('size='), undefined, {
      timeout: 3000,
    });
    return new URL(page.url()).search;
  });

  await check(engine, 'phone: index filter starts closed', async () => {
    await page.goto(`${base}/`, { waitUntil: 'networkidle' });
    await settle(page);
    const open = await page
      .locator('details.filter')
      .evaluate((d) => (d as HTMLDetailsElement).open);
    assert(!open, 'filter open');
  });

  // Firefox refuses pointer capture for the synthetic touches above, which no real finger meets.
  const real = errors.filter((e) => !e.includes('setPointerCapture'));
  record(engine, 'phone: no console errors', real.length === 0, real.slice(0, 5));
  await ctx.close();
}

async function siteFlows(engine: string, ctx: BrowserContext) {
  const page = await ctx.newPage();
  const errors: string[] = [];
  watch(page, errors);
  await page.addInitScript(() => {
    const w = window as unknown as { __vt: { names: string[]; err?: string }[] };
    w.__vt = [];
    const start = Document.prototype.startViewTransition;
    if (!start) return;
    Document.prototype.startViewTransition = function (this: Document, arg: never) {
      const vt = start.call(this, arg);
      const rec: { names: string[]; err?: string } = { names: [] };
      w.__vt.push(rec);
      vt.ready
        .then(() => {
          rec.names = document
            .getAnimations()
            .map((a) => (a.effect as KeyframeEffect | null)?.pseudoElement ?? '')
            .filter(Boolean);
        })
        .catch((e) => {
          rec.err = String(e);
        });
      return vt;
    } as typeof start;
  });

  await check(engine, 'view transition: grid plate morphs into the page plate', async () => {
    await page.goto(`${base}/`, { waitUntil: 'networkidle' });
    await settle(page, 800);
    const link = page.locator('.grid > li a').nth(1);
    const slug = await page.locator('.grid > li').nth(1).getAttribute('data-slug');
    // Grid links prefetch the page on intent, so the pointer rests on the link as a visitor's would.
    await link.hover();
    await page.waitForTimeout(400);
    await link.click();
    await page.waitForURL(`**/${slug}`);
    await settle(page, 800);
    const vt = await page.evaluate(
      () => (window as unknown as { __vt: { names: string[]; err?: string }[] }).__vt,
    );
    const supported = await page.evaluate(() => 'startViewTransition' in document);
    if (!supported) return 'no View Transitions API in this engine';
    const names = vt.flatMap((v) => v.names);
    const ok = names.some((n) => n.includes(`plate-${slug}`));
    assert(ok, `transitions ${JSON.stringify(vt).slice(0, 300)}`);
    return `${slug}: ${[...new Set(names)].slice(0, 6).join(' ')}`;
  });

  await check(engine, 'view transition: back to the index', async () => {
    const slug = new URL(page.url()).pathname.slice(1);
    await page.evaluate(() => {
      (window as unknown as { __vt: unknown[] }).__vt = [];
    });
    await page.locator('nav a[href="/"]').first().click();
    await page.waitForURL(`${base}/`);
    await settle(page, 800);
    const vt = await page.evaluate(
      () => (window as unknown as { __vt: { names: string[]; err?: string }[] }).__vt,
    );
    const supported = await page.evaluate(() => 'startViewTransition' in document);
    if (!supported) return 'no View Transitions API';
    const names = vt.flatMap((v) => v.names);
    return `${slug}: ${names.some((n) => n.includes(`plate-${slug}`)) ? 'paired' : 'not paired'} ${JSON.stringify(vt).slice(0, 200)}`;
  });

  await check(engine, 'about page', async () => {
    const r = await page.goto(`${base}/about`, { waitUntil: 'networkidle' });
    assert(r?.status() === 200, `status ${r?.status()}`);
    const h1 = await page.locator('h1').first().textContent();
    return h1;
  });

  await check(engine, '404 page', async () => {
    const r = await page.goto(`${base}/no-such-piece`, { waitUntil: 'networkidle' });
    const text = await page.locator('main').textContent();
    const robots = await page
      .locator('meta[name=robots]')
      .getAttribute('content')
      .catch(() => null);
    return `status ${r?.status()}, robots ${robots}, "${text?.trim().slice(0, 80)}"`;
  });

  await check(engine, 'social card meta and image', async () => {
    await page.goto(`${base}/tartan`, { waitUntil: 'networkidle' });
    const og = await page.locator('meta[property="og:image"]').getAttribute('content');
    const alt = await page.locator('meta[property="og:image:alt"]').getAttribute('content');
    assert(og, 'no og:image');
    const r = await page.request.get(
      new URL(og).pathname.startsWith('/') ? `${base}${new URL(og).pathname}` : og,
    );
    assert(
      r.status() === 200 && r.headers()['content-type']?.includes('png'),
      `card ${r.status()}`,
    );
    return `${og} (${alt?.slice(0, 40)})`;
  });

  // The 404 page's own status is logged as a failed load.
  const real = errors.filter((e) => !e.includes('status of 404'));
  record(engine, 'site: no console errors', real.length === 0, real.slice(0, 5));
  await page.close();
}

const engines: [string, BrowserType][] = [
  ['chromium', chromium],
  ['firefox', firefox],
  ['webkit', webkit],
];
for (const [name, type] of engines) {
  if (only && !only.includes(name)) continue;
  const browser = await type.launch();
  for (const flow of [indexFlows, themeFlows, detailFlows, siteFlows]) {
    // A fresh context per flow, so no theme or storage carries over.
    const ctx = await browser.newContext({
      viewport: { width: 1400, height: 900 },
      deviceScaleFactor: 1,
      colorScheme: 'dark',
      acceptDownloads: true,
      ...(name === 'chromium' ? { permissions: ['clipboard-read', 'clipboard-write'] } : {}),
    });
    try {
      await flow(name, ctx);
    } catch (e) {
      record(name, `${flow.name} crashed`, false, (e as Error).message);
    }
    await ctx.close();
  }
  try {
    await phoneFlows(name, browser);
  } catch (e) {
    record(name, 'phoneFlows crashed', false, (e as Error).message);
  }
  await browser.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
for (const f of failed) console.log(`FAILED ${f.engine} ${f.check}: ${f.info ?? ''}`);
process.exit(failed.length ? 1 : 0);
