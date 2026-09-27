/**
 * CI's stale-artifact check (design.md, Build and CI): fails when the committed build output no longer
 * matches its inputs, since CI never runs Python.
 *
 *   pnpm check-artifacts [root]
 *
 * Checks, for the repo at `root` (default: this checkout):
 * 1. every piece's design_sha and the render-lib hash against slots.json and wallpapers/.render-lib.sha256;
 * 2. every template's sha256 (and slot count) against slots.json, and no template missing from it;
 * 3. wallpapers/index.json against meta.yaml and slots.json;
 * 4. `checked: <walldye version>` in every slots.json.
 * Prints each problem and exits 1 if there are any.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { designSha, loadMeta, renderLibSha, sha256, slugs, stampedRenderLibSha } from '../src/lib/hash';
import { isDraft, licenseOf } from '../src/lib/meta';
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

function checkPiece(root: string, slug: string, version: string, problems: string[]): string[] | null {
  const run = `run walldye build ${slug}`;
  const build = join(root, 'wallpapers', slug, 'build');
  let current: string | null = null;
  try {
    current = designSha(root, slug);
  } catch (e) {
    problems.push(`${slug}: ${(e as Error).message}`);
  }
  const path = join(build, 'slots.json');
  if (!existsSync(path)) {
    problems.push(`${slug}: not built (no build/slots.json): ${run}`);
    return null;
  }
  let slots: Slots;
  try {
    slots = readSlots(path);
  } catch (e) {
    problems.push(`${slug}: build/slots.json: ${(e as Error).message}: ${run}`);
    return null;
  }
  if (current !== null && slots.design_sha !== current) {
    problems.push(`${slug}: design_sha differs from the design and meta.yaml themes: ${run}`);
  }
  if (slots.checked !== version) {
    problems.push(`${slug}: slots.json was checked by walldye ${JSON.stringify(slots.checked ?? null)}, not ${version}: ${run}`);
  }
  const listed = new Set<string>();
  const aspects: string[] = [];
  for (const [key, entry] of entries(slots)) {
    const aspect = key.split('/')[0];
    if (!aspects.includes(aspect)) aspects.push(aspect);
    listed.add(entry.file);
    const file = join(build, entry.file);
    if (!existsSync(file)) {
      problems.push(`${slug}: build/${entry.file} (${key}) is missing: ${run}`);
      continue;
    }
    const bytes = readFileSync(file);
    if (sha256(bytes) !== entry.sha256) {
      problems.push(`${slug}: build/${entry.file} does not match its sha256 in slots.json (edited by hand?): ${run}`);
    } else {
      const n = findColours(bytes.toString('utf8')).length;
      if (n !== entry.n) problems.push(`${slug}: build/${entry.file} has ${n} colour slots, slots.json says ${entry.n} for ${key}`);
    }
  }
  if (!aspects.includes('16:9')) problems.push(`${slug}: slots.json has no 16:9 template: ${run}`);
  for (const name of existsSync(build) ? readdirSync(build).sort() : []) {
    if (TEMPLATE_NAME.test(name) && !listed.has(name)) problems.push(`${slug}: build/${name} is not in slots.json: ${run}`);
  }
  return aspects;
}

/** index.json text as walldye build writes it (Python json.dumps, indent 2), keys in `index` order. */
function indexText(index: Map<string, object>): string {
  if (!index.size) return '{}\n';
  const body = [...index].map(([slug, v]) => `  ${JSON.stringify(slug)}: ${JSON.stringify(v, null, 2).replace(/\n/g, '\n  ')}`);
  return `{\n${body.join(',\n')}\n}\n`;
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

  const expected = new Map<string, { aspects: string[]; draft: boolean; license: unknown; title: unknown }>();
  let complete = true;
  for (const slug of slugs(root)) {
    const aspects = checkPiece(root, slug, version, problems);
    let meta: Record<string, unknown>;
    try {
      meta = loadMeta(root, slug);
    } catch (e) {
      problems.push(`${slug}: ${(e as Error).message}`);
      complete = false;
      continue;
    }
    if (aspects === null) complete = false;
    expected.set(slug, { aspects: aspects ?? [], draft: isDraft(meta), license: licenseOf(meta), title: meta.title ?? null });
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
    if (!expected.has(slug)) problems.push(`wallpapers/index.json lists ${slug}, which has no meta.yaml: run walldye build`);
  }
  for (const [slug, want] of expected) {
    const got = index[slug];
    if (!got) {
      problems.push(`wallpapers/index.json leaves out ${slug}: run walldye build ${slug}`);
      continue;
    }
    for (const field of ['draft', 'license', 'title', 'aspects'] as const) {
      if (field === 'aspects' && !want.aspects.length) continue;
      if (JSON.stringify(got[field] ?? null) !== JSON.stringify(want[field])) {
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
