/**
 * Every piece's 16:9 template through the plate's real rule, against recolor() as an `<img>`, in
 * Chromium, Firefox and WebKit: a template with `<defs>` is inlined in the plate (same-document
 * `<use>`), any other is an external `<use>`. The theme cycles through the presets so both regimes
 * and every template are covered. Prints the failures and writes their diffs.
 *
 * Usage: scripts/with-browsers.sh pnpm tsx scripts/spike/bulk.ts [outDir]
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { join, resolve } from 'node:path';
import { chromium, firefox, webkit } from '@playwright/test';
import { PNG } from 'pngjs';
import { motifTransform } from '../../src/lib/motif';
import { recolor, type SlotsEntry } from '../../src/lib/recolor';
import { partId, seedVars, toVarTemplate } from '../../src/lib/template-vars';
import { PRESETS, type Regime, regimeOf, type Seeds } from '../../src/lib/theme';

const WALLPAPERS = resolve(import.meta.dirname, '../../../wallpapers');
const OUT = resolve(process.argv[2] ?? join(process.env.CLAUDE_JOB_DIR ?? '.', 'tmp', 'bulk'));
const W = 640;
const H = 360;
const THEMES = Object.keys(PRESETS).filter((n) => n !== 'fireproof');

interface Item {
  slug: string;
  mode: 'ext' | 'inline';
  theme: string;
}

function build(): Item[] {
  rmSync(OUT, { recursive: true, force: true });
  mkdirSync(join(OUT, 't'), { recursive: true });
  const items: Item[] = [];
  const slugs = readdirSync(WALLPAPERS).filter((s) =>
    existsSync(join(WALLPAPERS, s, 'build', 'slots.json')),
  );
  slugs.sort().forEach((slug, i) => {
    const dir = join(WALLPAPERS, slug, 'build');
    const slots = JSON.parse(readFileSync(join(dir, 'slots.json'), 'utf8'));
    const theme = THEMES[i % THEMES.length];
    const seeds = PRESETS[theme] as Seeds;
    const regime = regimeOf(seeds);
    const entry = slots[`16:9/${regime}`] as SlotsEntry;
    const entries: Partial<Record<Regime, SlotsEntry>> = {};
    for (const r of ['dark', 'light'] as const) {
      if (slots[`16:9/${r}`].file === entry.file) entries[r] = slots[`16:9/${r}`];
    }
    const svg = readFileSync(join(dir, entry.file), 'utf8');
    const hash = slug.replace(/-/g, '');
    const v = toVarTemplate(svg, entries, hash);
    const mode = svg.includes('<defs>') ? 'inline' : 'ext';
    writeFileSync(join(OUT, 't', `${slug}.svg`), v.svg);
    writeFileSync(join(OUT, 't', `${slug}.ref.svg`), recolor(svg, entry, seeds));
    const href = (part: 'base' | 'motif') =>
      `${mode === 'ext' ? `t/${slug}.svg` : ''}#${partId(hash, part)}`;
    const motif = entry.motif
      ? `<g transform="${motifTransform({ x: entry.motif.at[0], y: entry.motif.at[1], k: 1 })}"><use href="${href('motif')}"/></g>`
      : '';
    const defs =
      mode === 'inline'
        ? `<defs>${v.svg.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')}</defs>`
        : '';
    const vars = Object.entries(seedVars(seeds))
      .map(([k, val]) => `${k}:${val}`)
      .join(';');
    const head = `<!doctype html><html style="${vars}"><head><meta charset="utf-8"><style>html,body{margin:0}#box{display:block;width:${W}px;height:${H}px}</style></head><body>`;
    writeFileSync(join(OUT, `${slug}.ref.html`), `${head}<img id="box" src="t/${slug}.ref.svg">`);
    writeFileSync(
      join(OUT, `${slug}.plate.html`),
      `${head}<svg id="box" viewBox="0 0 1920 1080">${defs}<use href="${href('base')}"/>${motif}</svg>`,
    );
    items.push({ slug, mode, theme });
  });
  return items;
}

function diff(a: Buffer, b: Buffer): { bad: number; max: number; png: Buffer } {
  const pa = PNG.sync.read(a);
  const pb = PNG.sync.read(b);
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
    out.data[i + 3] = 255;
  }
  return { bad, max, png: PNG.sync.write(out) };
}

const items = build();
const server = createServer((req, res) => {
  const path = decodeURIComponent((req.url ?? '/').split('?')[0]);
  const file = join(OUT, path);
  if (!existsSync(file) || path.endsWith('/')) {
    res.writeHead(404).end();
    return;
  }
  const type = path.endsWith('.svg') ? 'image/svg+xml' : 'text/html; charset=utf-8';
  res.writeHead(200, { 'content-type': type }).end(readFileSync(file));
});
await new Promise<void>((ok) => server.listen(0, '127.0.0.1', ok));
const base = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
const summary: Record<string, unknown> = {};
for (const type of [chromium, firefox, webkit]) {
  const browser = await type.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  const fails: string[] = [];
  for (const it of items) {
    const shot = async (kind: string) => {
      await page.goto(`${base}/${it.slug}.${kind}.html`, { waitUntil: 'load' });
      await page.waitForTimeout(100);
      return page.locator('#box').screenshot();
    };
    const d = diff(await shot('ref'), await shot('plate'));
    // Antialiasing seams between an <img> and inline SVG raster stay under 0.2% of the plate.
    if (d.bad > W * H * 0.002) {
      fails.push(`${it.slug} (${it.mode}, ${it.theme}): ${d.bad}px max ${d.max}`);
      writeFileSync(join(OUT, `${type.name()}-${it.slug}.diff.png`), d.png);
    }
  }
  await browser.close();
  summary[type.name()] = { checked: items.length, failed: fails.length, fails };
}
server.close();
const inline = items.filter((i) => i.mode === 'inline').length;
console.log(JSON.stringify({ inline, external: items.length - inline, ...summary }, null, 1));
