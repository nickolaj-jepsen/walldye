/**
 * Page views from Cloudflare Web Analytics, one file per UTC day, and the totals the index sorts by.
 * No imports, so `node` can run it from scripts/views/fetch.ts.
 */

/** One UTC day's page views by slug. */
export type Day = Record<string, number>;

/** Days over which a view's weight in `recent` halves. */
export const HALF_LIFE_DAYS = 7;

/** A day file's name: `YYYY-MM-DD.json`. */
export const DAY_FILE = /^(\d{4}-\d{2}-\d{2})\.json$/;

const SLUG_PATH = /^\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/;
const RENAME = /^\/([^/\s]+)\s+\/([^/\s]+)\s+301$/;
const DAY_MS = 86_400_000;

/** The slug a page path names (`/schotter` or `/schotter/`), else undefined. */
export function pathSlug(path: string): string | undefined {
  return SLUG_PATH.exec(path)?.[1];
}

/** `iso` (`YYYY-MM-DD`) as days since 1970-01-01 UTC. */
export function dayNumber(iso: string): number {
  return Date.parse(`${iso}T00:00:00Z`) / DAY_MS;
}

/** Day number `n` as `YYYY-MM-DD`. */
export function isoDay(n: number): string {
  return new Date(n * DAY_MS).toISOString().slice(0, 10);
}

/** A day file's JSON as a Day; throws unless it is an object of non-negative integer counts. */
export function parseDay(text: string): Day {
  const data: unknown = JSON.parse(text);
  if (typeof data !== 'object' || data === null || Array.isArray(data)) throw new Error('must be an object of slug: views');
  for (const [slug, n] of Object.entries(data)) {
    if (!Number.isInteger(n) || (n as number) < 0) throw new Error(`${slug}: views must be a non-negative integer`);
  }
  return data as Day;
}

/** Old slug to new slug, from the `/<old> /<new> 301` lines of public/_redirects. */
export function renames(text: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const line of text.split('\n')) {
    const m = RENAME.exec(line.trim());
    if (m) out.set(m[1], m[2]);
  }
  return out;
}

export interface Views {
  /** Every recorded view. */
  views: number;
  /** Views weighted by 2^(-age / HALF_LIFE_DAYS), age in days before the newest day on record. */
  recent: number;
}

/**
 * Each slug's Views over `days` (date to Day). A renamed slug's views count for the slug it
 * redirects to, following chains; a redirect loop leaves the slugs in it as they are.
 */
export function viewTotals(days: ReadonlyMap<string, Day>, renamed: ReadonlyMap<string, string> = new Map()): Map<string, Views> {
  const current = (slug: string) => {
    const seen = new Set<string>();
    let s = slug;
    while (renamed.has(s) && !seen.has(s)) {
      seen.add(s);
      s = renamed.get(s)!;
    }
    return seen.has(s) ? slug : s;
  };
  const dates = [...days.keys()];
  const newest = Math.max(...dates.map(dayNumber));
  const out = new Map<string, Views>();
  for (const [date, day] of days) {
    const weight = 2 ** (-(newest - dayNumber(date)) / HALF_LIFE_DAYS);
    for (const [slug, n] of Object.entries(day)) {
      const key = current(slug);
      const v = out.get(key) ?? { views: 0, recent: 0 };
      v.views += n;
      v.recent += n * weight;
      out.set(key, v);
    }
  }
  return out;
}
