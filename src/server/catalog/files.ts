/** The repo files the catalog reads besides the pieces: featured.yaml and the page views. */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { DAY_FILE, type Day, parseDay, renames, type Views, viewTotals } from '../views';
import { parseYaml } from '../yaml';

// Astro runs from the project root (as Base.astro assumes); this module is bundled, so import.meta.url is no anchor.
export const ROOT = resolve('.');
export const WALLPAPERS = join(ROOT, 'wallpapers');
/** The `stats` branch's day files, checked out by CI; absent locally unless fetched. */
const VIEWS = join(ROOT, 'stats', 'views');
/** The index's featured pieces, in order. */
export const FEATURED = join(WALLPAPERS, 'featured.yaml');

/** `path` relative to the project root, with forward slashes; the endpoints read files by it. */
export const rootPath = (path: string) => relative(ROOT, path).split(sep).join('/');

/**
 * Place by slug on featured.yaml, from 0; empty without the file. Throws when it is not a list of
 * slugs, names one twice, or names a folder that is not among `slugs`.
 */
export function loadFeatured(
  slugs: readonly string[],
  file: string = FEATURED,
): Map<string, number> {
  if (!existsSync(file)) return new Map();
  const list: unknown = parseYaml(readFileSync(file, 'utf8')) ?? [];
  if (!Array.isArray(list) || !list.every((s) => typeof s === 'string'))
    throw new Error('featured.yaml: must be a list of slugs');
  const out = new Map<string, number>();
  for (const [i, slug] of list.entries()) {
    if (out.has(slug)) throw new Error(`featured.yaml: ${slug} is listed twice`);
    if (!slugs.includes(slug))
      throw new Error(`featured.yaml: ${slug} is not a folder in wallpapers/`);
    out.set(slug, i);
  }
  return out;
}

/** Views by slug from VIEWS, renames in public/_redirects folded in; empty without VIEWS. Throws naming a malformed file. */
export function loadViews(): Map<string, Views> {
  if (!existsSync(VIEWS)) return new Map();
  const days = new Map<string, Day>();
  for (const file of readdirSync(VIEWS).sort()) {
    const date = DAY_FILE.exec(file)?.[1];
    if (!date) continue;
    try {
      days.set(date, parseDay(readFileSync(join(VIEWS, file), 'utf8')));
    } catch (e) {
      throw new Error(`${rootPath(join(VIEWS, file))}: ${(e as Error).message}`);
    }
  }
  const redirects = join(ROOT, 'public', '_redirects');
  return viewTotals(
    days,
    existsSync(redirects) ? renames(readFileSync(redirects, 'utf8')) : new Map(),
  );
}
