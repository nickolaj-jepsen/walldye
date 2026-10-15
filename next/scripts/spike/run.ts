/**
 * The external-<use> spike: renders build templates rewritten by toVarTemplate() through
 * `<svg><use href="/t/x.svg#base"/></svg>` with the seed variables on :root, and the same template
 * recolored by recolor() as an `<img>` (what the Astro site shows), in Chromium, Firefox and
 * WebKit, and compares the pixels. Also checks a live theme change and whether a hidden `<use>`
 * fetches its file.
 *
 * Usage: pnpm spike [outDir]   (browsers from PLAYWRIGHT_BROWSERS_PATH, as the repo dev shell sets)
 */
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { join, resolve } from 'node:path';
import { type BrowserType, chromium, firefox, webkit } from '@playwright/test';
import { PNG } from 'pngjs';
import { motifTransform, type Placement, placeMotif } from '../../src/lib/motif';
import { recolor, type SlotsEntry } from '../../src/lib/recolor';
import {
  bake,
  partId,
  seedVars,
  toVarTemplate,
  type VarTemplate,
} from '../../src/lib/template-vars';
import { parseToken, type Regime, regimeOf, type Seeds } from '../../src/lib/theme';

const WALLPAPERS = resolve(import.meta.dirname, '../../../wallpapers');
const OUT = resolve(process.argv[2] ?? join(process.env.CLAUDE_JOB_DIR ?? '.', 'tmp', 'spike'));
const W = 960;
const H = 540;

interface Case {
  name: string;
  slug: string;
  theme: string;
  /** The theme a live page starts in before switching to `theme`. */
  from?: string;
  place?: Placement;
  why: string;
}

const CASES: Case[] = [
  {
    name: 'moon-light',
    slug: 'dither-moon',
    theme: 'catppuccin-latte',
    why: 'motif, pixel, own light file',
  },
  {
    name: 'moon-dark-placed',
    slug: 'dither-moon',
    theme: 'nord',
    place: { x: 700, y: 600, k: 1.5 },
    why: 'motif moved and scaled',
  },
  { name: 'pond-mask', slug: 'pond-ripples', theme: 'dracula', why: 'mask with gradient' },
  {
    name: 'pond-mask-light',
    slug: 'pond-ripples',
    theme: 'gruvbox-light',
    from: 'dracula',
    why: 'shared file, live switch dark to light',
  },
  {
    name: 'planet-radial',
    slug: 'planet-with-moon',
    theme: 'gruvbox-dark',
    why: 'themed radial + linear gradients, masks',
  },
  { name: 'tartan-pattern', slug: 'tartan', theme: 'tokyo-night', why: 'themed patterns' },
  {
    name: 'tartan-light',
    slug: 'tartan',
    theme: 'rose-pine-dawn',
    why: 'themed patterns, light regime',
  },
  {
    name: 'accretion-clip',
    slug: 'accretion-disk',
    theme: 'solarized-light',
    why: 'clipPath, light regime',
  },
  {
    name: 'triangle-motif-defs',
    slug: 'impossible-triangle',
    theme: 'ffffff-000000-0000ff',
    place: { x: 900, y: 500, k: 0.8 },
    why: 'overscan motif using a themed pattern',
  },
  { name: 'kintsugi', slug: 'kintsugi', theme: 'everforest-dark', why: 'themed gradients' },
];

type Mode = 'ext' | 'sprite';

interface Loaded {
  svg: string;
  entry: SlotsEntry;
  seeds: Seeds;
  var: VarTemplate;
  hash: string;
}

function load(c: Case): Loaded {
  const dir = join(WALLPAPERS, c.slug, 'build');
  const slots = JSON.parse(readFileSync(join(dir, 'slots.json'), 'utf8'));
  const seeds = parseToken(c.theme);
  if (!seeds) throw new Error(c.theme);
  const regime = regimeOf(seeds);
  const entry = slots[`16:9/${regime}`] as SlotsEntry;
  const entries: Partial<Record<Regime, SlotsEntry>> = {};
  for (const r of ['dark', 'light'] as const) {
    if (slots[`16:9/${r}`].file === entry.file) entries[r] = slots[`16:9/${r}`];
  }
  const svg = readFileSync(join(dir, entry.file), 'utf8');
  const hash = c.name.replace(/[^a-z0-9]/g, '');
  return { svg, entry, seeds, var: toVarTemplate(svg, entries, hash), hash };
}

const rootVars = (seeds: Seeds) =>
  Object.entries(seedVars(seeds))
    .map(([k, v]) => `${k}:${v}`)
    .join(';');

const page = (body: string, seeds: Seeds) =>
  `<!doctype html><html style="${rootVars(seeds)}"><head><meta charset="utf-8"><style>
html,body{margin:0;background:#888}#box{width:${W}px;height:${H}px;display:block}
.hidden{display:none}</style></head><body>${body}</body></html>`;

/** The plate: an external <use>, or for `sprite` a same-document <use> of the file inlined in the plate's <defs>. */
function plate(c: Case, l: Loaded, mode: Mode): string {
  const file = `t/${c.name}.svg`;
  const href = (part: 'base' | 'motif') =>
    mode === 'ext' ? `${file}#${partId(l.hash, part)}` : `#${partId(l.hash, part)}`;
  const info = l.entry.motif;
  const motif =
    info &&
    `<g transform="${motifTransform(c.place ?? { x: info.at[0], y: info.at[1], k: 1 })}"><use href="${href('motif')}"/></g>`;
  const defs =
    mode === 'sprite'
      ? `<defs>${l.var.svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')}</defs>`
      : '';
  return `<svg id="box" viewBox="0 0 1920 1080" width="${W}" height="${H}">${defs}<use href="${href('base')}"/>${motif ?? ''}</svg>`;
}

function build(): void {
  rmSync(OUT, { recursive: true, force: true });
  mkdirSync(join(OUT, 't'), { recursive: true });
  for (const c of CASES) {
    const l = load(c);
    writeFileSync(join(OUT, 't', `${c.name}.svg`), l.var.svg);
    let ref = recolor(l.svg, l.entry, l.seeds);
    if (c.place) ref = placeMotif(ref, c.place);
    writeFileSync(join(OUT, 't', `${c.name}.ref.svg`), ref);
    writeFileSync(
      join(OUT, `${c.name}.ref.html`),
      page(`<img id="box" src="t/${c.name}.ref.svg" width="${W}" height="${H}">`, l.seeds),
    );
    for (const mode of ['ext', 'sprite'] as const) {
      writeFileSync(join(OUT, `${c.name}.${mode}.html`), page(plate(c, l, mode), l.seeds));
      // Starts in fireproof; the test switches the variables to the case's theme.
      writeFileSync(
        join(OUT, `${c.name}.${mode}.live.html`),
        page(plate(c, l, mode), parseToken(c.from ?? 'fireproof') as Seeds),
      );
    }
    // bake() must give recolor()'s text colors.
    const rows = { vars: l.var.vars, coefs: { [regimeOf(l.seeds)]: l.entry.coefs } };
    const baked = bake(l.var.svg, rows, l.seeds, c.place);
    writeFileSync(join(OUT, 't', `${c.name}.baked.svg`), baked);
    writeFileSync(
      join(OUT, `${c.name}.baked.html`),
      page(`<img id="box" src="t/${c.name}.baked.svg" width="${W}" height="${H}">`, l.seeds),
    );
  }
  // A hidden <use> next to a shown one: does the hidden file get fetched?
  const pond = readFileSync(join(OUT, 't', 'pond-mask.svg'));
  writeFileSync(join(OUT, 't', 'hidden.svg'), pond);
  writeFileSync(join(OUT, 't', 'hidden-use.svg'), pond);
  const id = partId('pondmask', 'base');
  writeFileSync(
    join(OUT, 'hidden.html'),
    page(
      `<svg id="box" viewBox="0 0 1920 1080" width="${W}" height="${H}"><use href="t/pond-mask.svg#${id}"/><use class="hidden" href="t/hidden-use.svg#${id}"/></svg>` +
        `<svg class="hidden" viewBox="0 0 1920 1080" width="${W}" height="${H}"><use href="t/hidden.svg#${id}"/></svg>`,
      parseToken('dracula') as Seeds,
    ),
  );
}

function serve(log: string[]): Promise<{ url: string; close: () => void }> {
  const server = createServer((req, res) => {
    const path = decodeURIComponent((req.url ?? '/').split('?')[0]);
    log.push(path);
    try {
      const body = readFileSync(join(OUT, path));
      const type = path.endsWith('.svg') ? 'image/svg+xml' : 'text/html; charset=utf-8';
      res.writeHead(200, { 'content-type': type, 'cache-control': 'no-store' });
      res.end(body);
    } catch {
      res.writeHead(404).end();
    }
  });
  return new Promise((ok) =>
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address() as { port: number };
      ok({ url: `http://127.0.0.1:${port}`, close: () => server.close() });
    }),
  );
}

interface Diff {
  /** Pixels whose largest channel difference exceeds 8. */
  bad: number;
  /** Largest channel difference anywhere. */
  max: number;
}

function diff(a: Buffer, b: Buffer, save?: string): Diff {
  const pa = PNG.sync.read(a);
  const pb = PNG.sync.read(b);
  if (pa.width !== pb.width || pa.height !== pb.height) throw new Error('size mismatch');
  const out = new PNG({ width: pa.width, height: pa.height });
  let bad = 0;
  let max = 0;
  for (let i = 0; i < pa.data.length; i += 4) {
    let m = 0;
    for (let ch = 0; ch < 3; ch++) m = Math.max(m, Math.abs(pa.data[i + ch] - pb.data[i + ch]));
    max = Math.max(max, m);
    if (m > 8) bad++;
    out.data[i] = m > 8 ? 255 : 0;
    out.data[i + 1] = Math.min(255, m * 16);
    out.data[i + 2] = 0;
    out.data[i + 3] = 255;
  }
  if (save && bad) writeFileSync(save, PNG.sync.write(out));
  return { bad, max };
}

const fmtDiff = (d: Diff) => (d.bad ? `FAIL ${d.bad}px max ${d.max}` : `ok (max ${d.max})`);

async function shoot(
  type: BrowserType,
  base: string,
  log: string[],
): Promise<Record<string, unknown>> {
  const browser = await type.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  const results: Record<string, unknown> = {};
  const grab = async (url: string) => {
    await p.goto(url, { waitUntil: 'load' });
    await p.waitForTimeout(250);
    return p.locator('#box').screenshot();
  };
  for (const c of CASES) {
    const name = `${type.name()}-${c.name}`;
    const ref = await grab(`${base}/${c.name}.ref.html`);
    writeFileSync(join(OUT, `${name}.ref.png`), ref);
    const row: Record<string, string> = { why: c.why };
    row.baked = fmtDiff(diff(ref, await grab(`${base}/${c.name}.baked.html`)));
    for (const mode of ['ext', 'sprite'] as const) {
      const shot = await grab(`${base}/${c.name}.${mode}.html`);
      writeFileSync(join(OUT, `${name}.${mode}.png`), shot);
      row[mode] = fmtDiff(diff(ref, shot, join(OUT, `${name}.${mode}.diff.png`)));
      await p.goto(`${base}/${c.name}.${mode}.live.html`, { waitUntil: 'load' });
      await p.waitForTimeout(250);
      const vars = seedVars(load(c).seeds);
      const ms = await p.evaluate((v) => {
        const t = performance.now();
        for (const [k, val] of Object.entries(v))
          document.documentElement.style.setProperty(k, val);
        return new Promise<number>((ok) =>
          requestAnimationFrame(() => requestAnimationFrame(() => ok(performance.now() - t))),
        );
      }, vars);
      row[`${mode}Live`] =
        `${fmtDiff(diff(ref, await p.locator('#box').screenshot()))}, ${Math.round(ms)}ms to 2nd frame`;
    }
    results[c.name] = row;
  }
  log.length = 0;
  await p.goto(`${base}/hidden.html`, { waitUntil: 'load' });
  await p.waitForTimeout(500);
  results.hiddenFetch = {
    displayNoneUse: log.includes('/t/hidden-use.svg'),
    useInDisplayNoneSvg: log.includes('/t/hidden.svg'),
  };
  await browser.close();
  return results;
}

async function main(): Promise<void> {
  build();
  const log: string[] = [];
  const { url, close } = await serve(log);
  const report: Record<string, unknown> = {};
  try {
    for (const type of [chromium, firefox, webkit]) {
      try {
        report[type.name()] = await shoot(type, url, log);
      } catch (e) {
        report[type.name()] = { error: (e as Error).message.split('\n')[0] };
      }
    }
  } finally {
    close();
  }
  writeFileSync(join(OUT, 'report.json'), JSON.stringify(report, null, 1));
  console.log(JSON.stringify(report, null, 1));
}

await main();
