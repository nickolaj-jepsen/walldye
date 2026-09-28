/**
 * Content hashes that tell CI when committed templates are stale, a port of walldye/tools/hashing.py.
 * Node only (fs, crypto, git); never import it from client code.
 *
 * Every hash is the sha256 of UTF-8 lines `<key>\t<value>\n` sorted by line; for a file the key is
 * its posix path relative to the repo root and the value the sha256 of its bytes.
 * src/lib/__fixtures__/hash-vector.json pins the definition for both sides.
 */

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';
import { DEFAULT_VARIANT } from './content';

export const RENDER_DEPS = ['numpy', 'scipy', 'shapely', 'scikit-image'] as const;
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Hex sha256 of `data` (a string is hashed as UTF-8). */
export function sha256(data: string | Uint8Array): string {
  return createHash('sha256').update(data).digest('hex');
}

/** Python's str ordering: by code point, not UTF-16 unit. */
export function compareCodePoints(a: string, b: string): number {
  const x = Array.from(a, (c) => c.codePointAt(0) as number);
  const y = Array.from(b, (c) => c.codePointAt(0) as number);
  for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}

/** sha256 of `lines` sorted, each terminated by a newline. */
export function digest(lines: readonly string[]): string {
  return sha256([...lines].sort(compareCodePoints).map((line) => `${line}\n`).join(''));
}

/** `<key>\t<sha256 of the file's bytes>`; `key` is the file's repo-relative posix path. */
export function fileLine(root: string, key: string): string {
  return `${key}\t${sha256(readFileSync(join(root, key)))}`;
}

/** meta.yaml text parsed the way PyYAML's safe_load reads it (YAML 1.1; duplicate keys, last wins). */
export function parseMeta(text: string): unknown {
  return parse(text, { version: '1.1', uniqueKeys: false });
}

/** wallpapers/<slug>/ of `root`; throws unless `slug` is lowercase words joined by single hyphens. */
export function pieceDir(root: string, slug: string): string {
  if (!SLUG.test(slug)) throw new Error(`bad slug ${JSON.stringify(slug)} (lowercase letters and digits, single hyphens)`);
  return join(root, 'wallpapers', slug);
}

/** Parsed wallpapers/<slug>/meta.yaml ({} when empty); throws naming the file unless it is a YAML mapping. */
export function loadMeta(root: string, slug: string): Record<string, unknown> {
  const path = join(pieceDir(root, slug), 'meta.yaml');
  let meta: unknown;
  try {
    meta = parseMeta(readFileSync(path, 'utf8'));
  } catch (e) {
    throw new Error(`${path}: not valid YAML: ${(e as Error).message}`);
  }
  if (meta === null || meta === undefined) return {};
  if (typeof meta !== 'object' || Array.isArray(meta)) throw new Error(`${path}: must be a mapping`);
  return meta as Record<string, unknown>;
}

/** Sorted names of every wallpapers/<slug>/ holding a meta.yaml. */
export function slugs(root: string): string[] {
  const dir = join(root, 'wallpapers');
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((name) => existsSync(join(dir, name, 'meta.yaml')))
    .sort(compareCodePoints);
}

/** True for a script-less piece (source.svg + palette.yaml); throws if it is neither kind. */
export function isLegacy(root: string, slug: string): boolean {
  const d = pieceDir(root, slug);
  if (existsSync(join(d, 'design.py'))) return false;
  if (existsSync(join(d, 'source.svg'))) return true;
  throw new Error(`${d} has neither design.py nor source.svg`);
}

/** Names of the regular files directly inside wallpapers/<slug>/data/, in code point order; [] without one. */
export function dataFiles(root: string, slug: string): string[] {
  const dir = join(pieceDir(root, slug), 'data');
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true })
    .filter((d) => d.isFile())
    .map((d) => d.name)
    .sort(compareCodePoints);
}

/** Hash lines of a piece: design.py (or source.svg and palette.yaml) and every file in data/. */
export function designLines(root: string, slug: string): string[] {
  const names = isLegacy(root, slug) ? ['source.svg', 'palette.yaml'] : ['design.py'];
  return [
    ...names.map((n) => fileLine(root, `wallpapers/${slug}/${n}`)),
    ...dataFiles(root, slug).map((n) => fileLine(root, `wallpapers/${slug}/data/${n}`)),
  ];
}

/** A version's hash lines: the piece's `lines`, plus `variant\t<name>` for a named variant. */
export function variantLines(lines: readonly string[], variant: string): string[] {
  return variant === DEFAULT_VARIANT ? [...lines] : [...lines, `variant\t${variant}`];
}

/** slots.json `design_sha` of a piece's `variant` as it is now. */
export function designSha(root: string, slug: string, variant = DEFAULT_VARIANT): string {
  return digest(variantLines(designLines(root, slug), variant));
}

function gitFiles(root: string, ...flags: string[]): string[] {
  const out = execFileSync('git', ['ls-files', '-z', ...flags, '--', 'walldye'], { cwd: root, encoding: 'utf8' });
  return out.split('\0').filter(Boolean);
}

/** `[name, version]` of every `[[package]]` in uv.lock text whose name is in `names`, in file order. */
export function lockedVersions(lock: string, names: readonly string[]): [string, string][] {
  const out: [string, string][] = [];
  let pkg: { name?: string; version?: string } | null = null;
  const flush = () => {
    if (pkg?.name !== undefined && names.includes(pkg.name)) {
      if (pkg.version === undefined) throw new Error(`uv.lock: ${pkg.name} has no version`);
      out.push([pkg.name, pkg.version]);
    }
  };
  let top = false;
  for (const line of lock.split(/\r?\n/)) {
    if (/^\s*\[\[package\]\]\s*$/.test(line)) {
      flush();
      pkg = {};
      top = true;
    } else if (/^\s*\[/.test(line)) {
      // A sub-table ([package.metadata]) or another top-level table: its keys are not the package's.
      top = false;
    } else if (pkg && top) {
      const m = /^(name|version)\s*=\s*"([^"]*)"/.exec(line);
      if (m && pkg[m[1] as 'name' | 'version'] === undefined) pkg[m[1] as 'name' | 'version'] = m[2];
    }
  }
  flush();
  return out;
}

/**
 * Hash lines of the render inputs: the walldye/ files in the git index, minus walldye/tools/** and
 * __pycache__; the RENDER_DEPS versions pinned in uv.lock; and .python-version. Untracked files never
 * count, except while nothing under walldye/ is tracked yet: then the files `git add walldye` would
 * stage stand in. Throws when uv.lock pins none of a RENDER_DEPS package or git fails.
 */
export function renderLibLines(root: string): string[] {
  let listed = gitFiles(root, '--cached');
  if (!listed.length) listed = gitFiles(root, '--others', '--exclude-standard');
  const files = [
    ...new Set(
      listed.filter((p) => {
        if (p.startsWith('walldye/tools/') || p.split('/').includes('__pycache__')) return false;
        try {
          return statSync(join(root, p)).isFile();
        } catch {
          return false;
        }
      }),
    ),
  ].sort(compareCodePoints);
  const pinned = lockedVersions(readFileSync(join(root, 'uv.lock'), 'utf8'), RENDER_DEPS);
  const missing = RENDER_DEPS.filter((d) => !pinned.some(([name]) => name === d));
  if (missing.length) throw new Error(`uv.lock pins none of: ${[...missing].sort().join(', ')}`);
  const python = readFileSync(join(root, '.python-version'), 'utf8').trim();
  return [...files.map((p) => fileLine(root, p)), ...pinned.map(([n, v]) => `dep\t${n}==${v}`), `python\t${python}`];
}

/** The render-lib hash as it is now; compare it with stampedRenderLibSha(). */
export function renderLibSha(root: string): string {
  return digest(renderLibLines(root));
}

/** The committed wallpapers/.render-lib.sha256, or null before the first stamp. */
export function stampedRenderLibSha(root: string): string | null {
  const path = join(root, 'wallpapers', '.render-lib.sha256');
  return existsSync(path) ? readFileSync(path, 'utf8').trim() : null;
}
