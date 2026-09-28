/**
 * CI's stale-artifact check (design.md, Build and CI): fails when the committed build output no longer
 * matches its inputs, since CI never runs Python.
 *
 *   pnpm check-artifacts [root]
 *
 * Checks, for the repo at `root` (default: this checkout):
 * 1. every version's design_sha against its slots.json, and the render-lib hash against wallpapers/.render-lib.sha256;
 * 2. every template's sha256 (and slot count) against its slots.json, and no template missing from it;
 * 3. a build/<variant>/ for each named variant in meta.yaml, with the default's set of templates, and
 *    no other directory in build/;
 * 4. wallpapers/index.json against meta.yaml and slots.json, listing exactly the built pieces;
 * 5. `checked: <walldye version>` in every slots.json.
 * Prints each problem and exits 1 if there are any.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DEFAULT_VARIANT, SITE_ASPECTS } from '../src/lib/content';
import { designLines, digest, loadMeta, renderLibSha, sha256, slugs, stampedRenderLibSha, variantLines } from '../src/lib/hash';
import { isDraft, licenseOf, namedVariants, variantsMeta, type NamedVariant } from '../src/lib/meta';
import { entries, type Slots } from '../src/lib/recolour';
import { findColours } from '../src/lib/tokenize';

const TEMPLATE_NAME = /^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)(\.light)?\.svg$/;

/** The walldye version pyproject.toml declares (what `walldye build` stamps as `checked`). */
export function walldyeVersion(root: string): string {
  let inProject = false;
  for (const line of readFileSync(join(root, 'pyproject.toml'), 'utf8').split(/\r?\n/)) {
    const table = /^\s*\[([^\]]+)\]\s*$/.exec(line);
    if (table) inProject = table[1].trim() === 'project';
    const m = inProject && /^version\s*=\s*"([^"]+)"/.exec(line);
    if (m) return m[1];
  }
  throw new Error('pyproject.toml has no [project] version');
}

function readSlots(path: string): Slots {
  const slots: unknown = JSON.parse(readFileSync(path, 'utf8'));
  if (typeof slots !== 'object' || slots === null || Array.isArray(slots)) throw new Error('not a JSON object');
  return slots as Slots;
}

/**
 * Checks one version's build directory (build/ for the default, build/<variant>/ otherwise) against
 * `lines`, the piece's hash lines (null when they could not be read). Returns its template keys
 * sorted, or null when it has no readable slots.json.
 */
function checkBuild(root: string, slug: string, variant: string, lines: string[] | null, version: string, problems: string[]): string[] | null {
  const run = `run walldye build ${slug}`;
  const named = variant !== DEFAULT_VARIANT;
  const rel = named ? `build/${variant}/` : 'build/';
  const dir = join(root, 'wallpapers', slug, rel);
  const path = join(dir, 'slots.json');
  if (!existsSync(path)) {
    problems.push(`${slug}: ${rel}slots.json is missing: ${run}`);
    return null;
  }
  let slots: Slots;
  try {
    slots = readSlots(path);
  } catch (e) {
    problems.push(`${slug}: ${rel}slots.json: ${(e as Error).message}: ${run}`);
    return null;
  }
  if (lines !== null && slots.design_sha !== digest(variantLines(lines, variant))) {
    problems.push(`${slug}: ${rel}slots.json has a stale design_sha (the design or its data changed): ${run}`);
  }
  if (named && slots.variant !== variant) {
    problems.push(`${slug}: ${rel}slots.json has variant ${JSON.stringify(slots.variant ?? null)}, not "${variant}": ${run}`);
  } else if (!named && slots.variant !== undefined) {
    problems.push(`${slug}: build/slots.json has variant ${JSON.stringify(slots.variant)}, but the default's has none: ${run}`);
  }
  if (slots.checked !== version) {
    problems.push(`${slug}: ${rel}slots.json was checked by walldye ${JSON.stringify(slots.checked ?? null)}, not ${version}: ${run}`);
  }
  // A light entry often names the dark template; each file is reported once.
  const listed = new Set<string>();
  const keys: string[] = [];
  for (const [key, entry] of entries(slots)) {
    keys.push(key);
    const seen = listed.has(entry.file);
    listed.add(entry.file);
    const file = join(dir, entry.file);
    if (!existsSync(file)) {
      if (!seen) problems.push(`${slug}: ${rel}${entry.file} (${key}) is missing: ${run}`);
      continue;
    }
    const bytes = readFileSync(file);
    if (sha256(bytes) !== entry.sha256) {
      if (!seen) problems.push(`${slug}: ${rel}${entry.file} does not match its sha256 in slots.json (edited by hand?): ${run}`);
    } else {
      const n = findColours(bytes.toString('utf8')).length;
      if (n !== entry.n) problems.push(`${slug}: ${rel}${entry.file} has ${n} colour slots, slots.json says ${entry.n} for ${key}`);
    }
  }
  if (!keys.some((k) => k.startsWith('16:9/'))) problems.push(`${slug}: ${rel}slots.json has no 16:9 template: ${run}`);
  for (const name of readdirSync(dir).sort()) {
    if (TEMPLATE_NAME.test(name) && !listed.has(name)) problems.push(`${slug}: ${rel}${name} is not in slots.json: ${run}`);
  }
  return keys.sort();
}

/**
 * Checks every version of a built piece; `named` are the variants its meta.yaml lists. Returns the
 * default version's aspects in SITE_ASPECTS order, or null when build/slots.json cannot be read.
 */
function checkPiece(root: string, slug: string, named: NamedVariant[], version: string, problems: string[]): string[] | null {
  const run = `run walldye build ${slug}`;
  let lines: string[] | null = null;
  try {
    lines = designLines(root, slug);
  } catch (e) {
    problems.push(`${slug}: ${(e as Error).message}`);
  }
  const keys = checkBuild(root, slug, DEFAULT_VARIANT, lines, version, problems);
  for (const { name } of named) {
    const got = checkBuild(root, slug, name, lines, version, problems);
    if (keys && got && got.join() !== keys.join()) {
      problems.push(`${slug}: build/${name}/ has templates for ${got.join(', ')}, build/ for ${keys.join(', ')}: ${run}`);
    }
  }
  const build = join(root, 'wallpapers', slug, 'build');
  const names = new Set(named.map((v) => v.name));
  for (const d of existsSync(build) ? readdirSync(build, { withFileTypes: true }) : []) {
    if (d.isDirectory() && !names.has(d.name)) problems.push(`${slug}: build/${d.name}/ is not a variant in meta.yaml: ${run}`);
  }
  return keys && SITE_ASPECTS.filter((a) => keys.some((k) => k.startsWith(`${a}/`)));
}

/** `value` as JSON with every object's keys sorted, so two values compare by content. */
function canonical(value: unknown): string {
  return JSON.stringify(value, (_, v: unknown) =>
    typeof v === 'object' && v !== null && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))) : v,
  );
}

/** index.json text as walldye build writes it (Python json.dumps, indent 2), keys in `index` order. */
function indexText(index: Map<string, object>): string {
  if (!index.size) return '{}\n';
  const body = [...index].map(([slug, v]) => `  ${JSON.stringify(slug)}: ${JSON.stringify(v, null, 2).replace(/\n/g, '\n  ')}`);
  return `{\n${body.join(',\n')}\n}\n`;
}

interface IndexEntry {
  aspects: string[];
  draft: boolean;
  license: unknown;
  title: unknown;
  variants: Record<string, { draft: boolean; label: string }>;
}

/** Every problem with the committed artifacts of the repo at `root`; [] when all are current. */
export function checkArtifacts(root: string): string[] {
  const problems: string[] = [];
  const version = walldyeVersion(root);
  const stamped = stampedRenderLibSha(root);
  if (stamped === null) {
    problems.push('wallpapers/.render-lib.sha256 is missing: run walldye build --all');
  } else if (stamped !== renderLibSha(root)) {
    problems.push('the render inputs (walldye/, uv.lock, .python-version) changed since wallpapers/.render-lib.sha256: run walldye build --all');
  }

  // Only built pieces belong in index.json; an unbuilt one is a problem of its own.
  const expected = new Map<string, IndexEntry>();
  const unbuilt = new Set<string>();
  const pieces = slugs(root);
  let complete = true;
  for (const slug of pieces) {
    let meta: Record<string, unknown> | null = null;
    try {
      meta = loadMeta(root, slug);
    } catch (e) {
      problems.push(`${slug}: ${(e as Error).message}`);
      complete = false;
    }
    if (meta?.variants !== undefined) {
      const parsed = variantsMeta.safeParse(meta.variants);
      for (const issue of parsed.error?.issues ?? []) {
        problems.push(`${slug}: meta.yaml variants${issue.path.map((p) => `.${String(p)}`).join('')}: ${issue.message}`);
      }
    }
    if (!existsSync(join(root, 'wallpapers', slug, 'build', 'slots.json'))) {
      problems.push(`${slug}: not built (no build/slots.json): run walldye build ${slug}`);
      unbuilt.add(slug);
      continue;
    }
    const named = meta ? namedVariants(meta) : [];
    const aspects = checkPiece(root, slug, named, version, problems);
    if (aspects === null) complete = false;
    if (!meta) continue;
    expected.set(slug, {
      aspects: aspects ?? [],
      draft: isDraft(meta),
      license: licenseOf(meta),
      title: meta.title ?? null,
      variants: Object.fromEntries(named.map((v) => [v.name, { draft: v.draft, label: typeof v.label === 'string' ? v.label : '' }])),
    });
  }

  const indexPath = join(root, 'wallpapers', 'index.json');
  if (!existsSync(indexPath)) {
    problems.push('wallpapers/index.json is missing: run walldye build');
    return problems;
  }
  const text = readFileSync(indexPath, 'utf8');
  let index: Record<string, Record<string, unknown>>;
  try {
    index = JSON.parse(text);
  } catch (e) {
    problems.push(`wallpapers/index.json: ${(e as Error).message}`);
    return problems;
  }
  const before = problems.length;
  for (const slug of Object.keys(index)) {
    if (!pieces.includes(slug)) problems.push(`wallpapers/index.json lists ${slug}, which has no meta.yaml: run walldye build`);
    else if (unbuilt.has(slug)) problems.push(`wallpapers/index.json lists ${slug}, which is not built: run walldye build ${slug}`);
  }
  for (const [slug, want] of expected) {
    const got = index[slug];
    if (!got) {
      problems.push(`wallpapers/index.json leaves out ${slug}: run walldye build ${slug}`);
      continue;
    }
    for (const field of ['draft', 'license', 'title', 'aspects', 'variants'] as const) {
      if (field === 'aspects' && !want.aspects.length) continue;
      if (canonical(got[field] ?? null) !== canonical(want[field])) {
        const source = field === 'aspects' ? 'slots.json' : 'meta.yaml';
        problems.push(
          `wallpapers/index.json: ${slug} ${field} is ${JSON.stringify(got[field] ?? null)}, ${source} says ${JSON.stringify(want[field])}: run walldye build ${slug}`,
        );
      }
    }
  }
  if (complete && problems.length === before && text !== indexText(expected)) {
    problems.push('wallpapers/index.json is not laid out the way walldye build writes it: run walldye build');
  }
  return problems;
}

function main(): void {
  const root = resolve(process.argv[2] ?? fileURLToPath(new URL('..', import.meta.url)));
  const problems = checkArtifacts(root);
  for (const p of problems) console.error(p);
  if (problems.length) {
    console.error(`check-artifacts: ${problems.length} problem${problems.length === 1 ? '' : 's'}`);
    process.exit(1);
  }
  console.log(`check-artifacts: ${slugs(root).length} pieces current`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
