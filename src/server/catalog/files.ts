/** The repo files the catalog reads besides the pieces: featured.yaml and the stats day files. */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import {
  DAY_FILE,
  type Day,
  parseDay,
  parseEvents,
  pieceTotals,
  renames,
  type Totals,
} from '../stats';
import { parseYaml } from '../yaml';

// Astro runs from the project root (as Base.astro assumes); this module is bundled, so import.meta.url is no anchor.
export const ROOT = resolve('.');
export const WALLPAPERS = join(ROOT, 'wallpapers');
/** The `stats` branch, checked out by CI; absent locally unless fetched. */
const STATS = join(ROOT, 'stats');
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

/** `<date>.json` in `dir` read by `parse`, by date; empty without `dir`. Throws naming a malformed file. */
function readDays<T>(dir: string, parse: (text: string) => T): Map<string, T> {
  const days = new Map<string, T>();
  if (!existsSync(dir)) return days;
  for (const file of readdirSync(dir).sort()) {
    const date = DAY_FILE.exec(file)?.[1];
    if (!date) continue;
    try {
      days.set(date, parse(readFileSync(join(dir, file), 'utf8')));
    } catch (e) {
      throw new Error(`${rootPath(join(dir, file))}: ${(e as Error).message}`);
    }
  }
  return days;
}

/**
 * Totals by slug from STATS's views and events day files, renames in public/_redirects folded in;
 * empty without STATS. Throws naming a malformed file.
 */
export function loadStats(): Map<string, Totals> {
  const views = readDays(join(STATS, 'views'), parseDay);
  const downloads = new Map<string, Day>();
  for (const [date, day] of readDays(join(STATS, 'events'), parseEvents))
    downloads.set(date, day.downloads);
  const redirects = join(ROOT, 'public', '_redirects');
  return pieceTotals(
    views,
    downloads,
    existsSync(redirects) ? renames(readFileSync(redirects, 'utf8')) : new Map(),
  );
}
