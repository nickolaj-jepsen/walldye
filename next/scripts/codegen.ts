/**
 * Prebuild: reads ../wallpapers (meta.yaml and build/), taxonomy.yaml, featured.yaml and
 * ../stats/views when present, and writes
 *
 * - public/t/<hash>.svg: each build file as a var template (src/lib/template-vars.ts), named by a
 *   hash of the file's sha256, the rows of each regime it serves and TEMPLATE_FORMAT;
 * - src/generated/catalog.json: the Catalog (src/lib/catalog.ts);
 * - src/generated/rows.json: each template's BakeRows, for export and social cards;
 * - src/generated/scripts/<slug>.py: each design.py, read by getScript() at build time only;
 * - src/generated/known-paths.json: the first path segment of every page, for worker.ts;
 * - public/sitemap.xml and public/robots.txt, for SITE_URL;
 * - src/generated/boot.ts: the theme boot (src/client/theme/boot.ts) as an inline-script string;
 * - public/favicon.svg: the icon in fireproof, switching to flexoki-light under a light scheme.
 *
 * Incremental: a template whose output file exists and is in src/generated/.codegen-cache.json is
 * not read again. Files in public/t that no piece names any more are removed.
 *
 * Usage: tsx scripts/codegen.ts [--drafts]   (also WALLDYE_DRAFTS=1)
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { build } from 'esbuild';
import type {
  Catalog,
  Piece,
  PlateRef,
  Plates,
  Source,
  Taxonomy,
  TemplateInfo,
  Version,
} from '../src/lib/catalog';
import { type Aspect, CANVAS, SITE_ASPECTS } from '../src/lib/content';
import { faviconSvg } from '../src/lib/favicon';
import { TAXONOMY_FACETS } from '../src/lib/labels';
import type { SlotsEntry } from '../src/lib/recolor';
import {
  type BakeRows,
  type EntryRows,
  TEMPLATE_FORMAT,
  toVarTemplate,
  type VarRows,
} from '../src/lib/template-vars';
import { PRESETS, type Regime } from '../src/lib/theme';
import { typesetMeta } from '../src/lib/typeset';
import {
  DEFAULT_LICENSE,
  DEFAULT_VARIANT,
  isDraft,
  isMapping,
  licenseOf,
  type Meta,
  namedVariants,
} from './codegen/meta';
import { renderNotes } from './codegen/notes';
import { DAY_FILE, type Day, parseDay, renames, type Views, viewTotals } from './codegen/views';
import { parseYaml } from './codegen/yaml';

const APP = resolve(import.meta.dirname, '..');
const REPO = resolve(APP, '..');
const WALLPAPERS = join(REPO, 'wallpapers');
const VIEWS = join(REPO, 'stats', 'views');
const PUBLIC_T = join(APP, 'public', 't');
const GENERATED = join(APP, 'src', 'generated');
const CACHE = join(GENERATED, '.codegen-cache.json');
const REGIMES: readonly Regime[] = ['dark', 'light'];

const drafts = process.argv.includes('--drafts') || process.env.WALLDYE_DRAFTS === '1';

const sha256 = (data: string | Buffer) => createHash('sha256').update(data).digest('hex');

interface Cached {
  vars: VarRows;
  inline: boolean;
}

/** Template facts by hash from the last run; a hash names its inputs, so an entry never goes stale. */
const cache: Record<string, Cached> = existsSync(CACHE)
  ? JSON.parse(readFileSync(CACHE, 'utf8'))
  : {};
const templates: Record<string, TemplateInfo> = {};
const rows: Record<string, BakeRows> = {};
let rewritten = 0;

/**
 * The var template of build file `file` in `dir`, which `entries` (the slots.json entries of each
 * regime using it) describe: written to public/t unless already there. Returns its hash.
 */
function template(
  slug: string,
  dir: string,
  aspect: Aspect,
  file: string,
  entries: Partial<Record<Regime, SlotsEntry>>,
): string {
  const first = (entries.dark ?? entries.light) as SlotsEntry;
  const shape: Partial<Record<Regime, EntryRows>> = {};
  for (const r of REGIMES) {
    const e = entries[r];
    if (e) shape[r] = { coefs: e.coefs, occ: e.occ, n: e.n };
  }
  const hash = sha256(`${TEMPLATE_FORMAT}\n${first.sha256}\n${JSON.stringify(shape)}`).slice(0, 12);
  const out = join(PUBLIC_T, `${hash}.svg`);
  let facts = cache[hash];
  if (!facts || !existsSync(out)) {
    const path = join(dir, file);
    if (!existsSync(path)) throw new Error(`${path} is missing: run walldye build ${slug}`);
    const svg = readFileSync(path, 'utf8');
    if (sha256(svg) !== first.sha256)
      throw new Error(`${path} differs from slots.json: run walldye build ${slug}`);
    const v = toVarTemplate(svg, shape, hash);
    writeFileSync(out, v.svg);
    facts = { vars: v.vars, inline: svg.includes('<defs>') };
    cache[hash] = facts;
    rewritten++;
  }
  templates[hash] = {
    inline: facts.inline,
    canvas: CANVAS[aspect],
    ...(first.motif ? { motif: first.motif } : {}),
  };
  const coefs: BakeRows['coefs'] = {};
  for (const r of REGIMES) if (entries[r]) coefs[r] = (entries[r] as SlotsEntry).coefs;
  rows[hash] = { vars: facts.vars, coefs };
  return hash;
}

interface Build {
  plates: Plates;
  focus: [number, number];
  motif: boolean;
}

/** One build directory's plates; throws naming the file when the build is missing or stale. */
function readBuild(slug: string, dir: string): Build {
  const slotsPath = join(dir, 'slots.json');
  if (!existsSync(slotsPath)) throw new Error(`${slotsPath} is missing: run walldye build ${slug}`);
  const slots = JSON.parse(readFileSync(slotsPath, 'utf8')) as Record<string, unknown>;
  const plates: Partial<Record<Aspect, PlateRef>> = {};
  for (const aspect of SITE_ASPECTS) {
    const byRegime = Object.fromEntries(
      REGIMES.map((r) => [r, slots[`${aspect}/${r}`] as SlotsEntry | undefined]),
    ) as Record<Regime, SlotsEntry | undefined>;
    if (!byRegime.dark) continue;
    if (!byRegime.light)
      throw new Error(`${slotsPath} has no ${aspect}/light template: run walldye build ${slug}`);
    const files = new Map<string, Partial<Record<Regime, SlotsEntry>>>();
    for (const r of REGIMES) {
      const e = byRegime[r] as SlotsEntry;
      files.set(e.file, { ...files.get(e.file), [r]: e });
    }
    const hashes = Object.fromEntries(
      [...files].flatMap(([file, entries]) => {
        const hash = template(slug, dir, aspect, file, entries);
        return Object.keys(entries).map((r) => [r, hash]);
      }),
    ) as unknown as PlateRef;
    plates[aspect] = { dark: hashes.dark, light: hashes.light };
  }
  if (!plates['16:9'])
    throw new Error(`${slotsPath} has no 16:9/dark template: run walldye build ${slug}`);
  const main = slots['16:9/dark'] as SlotsEntry;
  return {
    plates: plates as Plates,
    focus: (Array.isArray(slots.focus) ? slots.focus : [0.5, 0.5]) as [number, number],
    motif: Boolean(main.motif),
  };
}

function loadTaxonomy(): Taxonomy {
  const data = (parseYaml(readFileSync(join(WALLPAPERS, 'taxonomy.yaml'), 'utf8')) ?? {}) as Meta;
  const labels = (v: unknown) => (isMapping(v) ? (v as Record<string, string>) : {});
  const facets = {} as Taxonomy['facets'];
  for (const f of TAXONOMY_FACETS) facets[f] = labels(data[f]);
  return { facets, models: labels(data.models) };
}

/** Place by slug on featured.yaml, from 0; throws on a slug that is not a folder or is listed twice. */
function loadFeatured(slugs: readonly string[]): Map<string, number> {
  const file = join(WALLPAPERS, 'featured.yaml');
  if (!existsSync(file)) return new Map();
  const list = (parseYaml(readFileSync(file, 'utf8')) ?? []) as unknown[];
  if (!Array.isArray(list) || !list.every((s) => typeof s === 'string'))
    throw new Error('featured.yaml: must be a list of slugs');
  const out = new Map<string, number>();
  for (const [i, slug] of (list as string[]).entries()) {
    if (out.has(slug)) throw new Error(`featured.yaml: ${slug} is listed twice`);
    if (!slugs.includes(slug))
      throw new Error(`featured.yaml: ${slug} is not a folder in wallpapers/`);
    out.set(slug, i);
  }
  return out;
}

function loadViews(): Map<string, Views> {
  if (!existsSync(VIEWS)) return new Map();
  const days = new Map<string, Day>();
  for (const file of readdirSync(VIEWS).sort()) {
    const date = DAY_FILE.exec(file)?.[1];
    if (date) days.set(date, parseDay(readFileSync(join(VIEWS, file), 'utf8')));
  }
  const redirects = join(REPO, 'public', '_redirects');
  return viewTotals(
    days,
    existsSync(redirects) ? renames(readFileSync(redirects, 'utf8')) : new Map(),
  );
}

const text = (v: unknown) => (typeof v === 'string' ? v.trim() : '');
const list = (v: unknown) =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];

async function piece(
  slug: string,
  meta: Meta,
  featured: Map<string, number>,
  views: Map<string, Views>,
  scripts: Record<string, string>,
): Promise<Piece> {
  const dir = join(WALLPAPERS, slug);
  const main = readBuild(slug, join(dir, 'build'));
  const aspects = SITE_ASPECTS.filter((a) => main.plates[a]);
  const description = text(meta.description);
  const alt = text(meta.alt);
  const versions: Version[] = [];
  for (const v of namedVariants(meta)) {
    if (v.draft && !drafts) continue;
    let named: Build;
    try {
      named = readBuild(slug, join(dir, 'build', v.name));
    } catch (e) {
      if (!v.draft) throw e;
      console.warn(`skipping draft variant ${slug} ${v.name}: ${(e as Error).message}`);
      continue;
    }
    versions.push({
      name: v.name,
      label: text(v.label),
      description: text(v.description) || description,
      alt: text(v.alt) || alt,
      draft: v.draft,
      focus: named.focus,
      plates: named.plates,
    });
  }
  if (versions.length) {
    const variants = meta.variants as Record<string, { label?: unknown }>;
    versions.unshift({
      name: DEFAULT_VARIANT,
      label: text(variants[DEFAULT_VARIANT]?.label),
      description,
      alt,
      draft: false,
      focus: main.focus,
      plates: main.plates,
    });
  }
  const scriptPath = join(dir, 'design.py');
  const hasScript = existsSync(scriptPath);
  if (hasScript) scripts[slug] = readFileSync(scriptPath, 'utf8');
  const license = licenseOf(meta);
  const v = views.get(slug);
  const rank = featured.get(slug);
  const franchise = isMapping(meta.franchise)
    ? { title: text(meta.franchise.title), owner: text(meta.franchise.owner) }
    : undefined;
  return {
    slug,
    title: text(meta.title),
    description,
    alt,
    notesHtml: await renderNotes(meta.notes),
    technique: list(meta.technique),
    subject: list(meta.subject),
    lineage: list(meta.lineage),
    sources: (Array.isArray(meta.sources) ? meta.sources : []) as Source[],
    added: String(meta.added),
    ...(meta.author ? { author: text(meta.author) } : {}),
    ...(meta.model ? { model: text(meta.model) } : {}),
    ...(meta.license ? { license: String(meta.license) } : {}),
    ...(franchise ? { franchise } : {}),
    draft: isDraft(meta),
    resolvedLicense: typeof license === 'string' ? license : DEFAULT_LICENSE,
    hasScript,
    hasData: existsSync(join(dir, 'data')),
    aspects,
    focus: main.focus,
    motif: main.motif,
    plates: main.plates,
    versions,
    views: v?.views ?? 0,
    recent: Math.round((v?.recent ?? 0) * 100) / 100,
    ...(rank === undefined ? {} : { featured: rank }),
  };
}

/** The theme boot bundled as a minified IIFE, for the root layout's inline `<head>` script. */
async function writeBoot(): Promise<void> {
  const out = await build({
    entryPoints: [join(APP, 'src', 'client', 'theme', 'boot.ts')],
    bundle: true,
    format: 'iife',
    minify: true,
    write: false,
    target: 'es2022',
  });
  const js = out.outputFiles[0].text.trim();
  writeFileSync(
    join(GENERATED, 'boot.ts'),
    `/** Generated by scripts/codegen.ts from src/client/theme/boot.ts. */\nexport const THEME_BOOT = ${JSON.stringify(js)};\n`,
  );
}

/** design.py of each piece that has one, as src/generated/scripts/<slug>.py; no other file stays. */
function writeScripts(scripts: Record<string, string>): void {
  const dir = join(GENERATED, 'scripts');
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir);
  for (const [slug, text] of Object.entries(scripts)) writeFileSync(join(dir, `${slug}.py`), text);
}

/** The sitemap (the index, about and each published piece) and robots.txt, which names it. */
function writeCrawlFiles(pieces: readonly Piece[]): void {
  const site = process.env.SITE_URL || 'https://walldye.com';
  const paths = ['/', '/about', ...pieces.filter((p) => !p.draft).map((p) => `/${p.slug}`)];
  const urls = paths.map((path) => `<url>\n<loc>${new URL(path, site).href}</loc>\n</url>`);
  writeFileSync(
    join(APP, 'public', 'sitemap.xml'),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`,
  );
  writeFileSync(
    join(APP, 'public', 'robots.txt'),
    `User-Agent: *\nAllow: /\n\nSitemap: ${new URL('/sitemap.xml', site).href}\n`,
  );
}

async function main(): Promise<void> {
  const t0 = performance.now();
  mkdirSync(PUBLIC_T, { recursive: true });
  mkdirSync(GENERATED, { recursive: true });
  const slugs = readdirSync(WALLPAPERS, { withFileTypes: true })
    .filter((d) => d.isDirectory() && existsSync(join(WALLPAPERS, d.name, 'meta.yaml')))
    .map((d) => d.name)
    .sort();
  await writeBoot();
  writeFileSync(
    join(APP, 'public', 'favicon.svg'),
    faviconSvg(PRESETS.fireproof, PRESETS['flexoki-light']),
  );
  const featured = loadFeatured(slugs);
  const views = loadViews();
  const scripts: Record<string, string> = {};
  const pieces: Piece[] = [];
  for (const slug of slugs) {
    const path = join(WALLPAPERS, slug, 'meta.yaml');
    const meta = typesetMeta((parseYaml(readFileSync(path, 'utf8')) ?? {}) as Meta);
    if (!isMapping(meta)) throw new Error(`${path}: must be a mapping`);
    if (isDraft(meta) && !drafts) continue;
    try {
      pieces.push(await piece(slug, meta, featured, views, scripts));
    } catch (e) {
      // A draft mid-build must not stop the others.
      if (!isDraft(meta)) throw e;
      console.warn(`skipping draft ${slug}: ${(e as Error).message}`);
    }
  }
  const catalog: Catalog = { pieces, templates, taxonomy: loadTaxonomy(), drafts };
  writeFileSync(join(GENERATED, 'catalog.json'), JSON.stringify(catalog));
  writeFileSync(join(GENERATED, 'rows.json'), JSON.stringify(rows));
  writeScripts(scripts);
  writeFileSync(
    join(GENERATED, 'known-paths.json'),
    JSON.stringify(['about', ...pieces.map((p) => p.slug)]),
  );
  writeCrawlFiles(pieces);
  const keep = new Set(Object.keys(templates));
  let removed = 0;
  for (const f of readdirSync(PUBLIC_T)) {
    if (!keep.has(f.replace(/\.svg$/, ''))) {
      rmSync(join(PUBLIC_T, f));
      removed++;
    }
  }
  for (const h of Object.keys(cache)) if (!keep.has(h)) delete cache[h];
  writeFileSync(CACHE, JSON.stringify(cache));
  const inline = Object.values(templates).filter((t) => t.inline).length;
  console.log(
    `codegen: ${pieces.length} pieces${drafts ? ' (drafts included)' : ''}, ` +
      `${keep.size} templates (${inline} inline, ${rewritten} rewritten, ${removed} removed) ` +
      `in ${Math.round(performance.now() - t0)} ms`,
  );
}

await main();
