/**
 * The `stats` branch's day files and the totals the index sorts by. `views/<date>.json` holds a UTC
 * day's page views from Cloudflare Web Analytics and `events/<date>.json` its product events from
 * Analytics Engine. Its import from src/lib names the file with its extension, so `node` can run it
 * from scripts/stats/.
 */
import * as z from 'zod/mini';
import {
  CONTEXT_FIELDS,
  EVENT_FIELDS,
  type EventName,
  FIELDS,
  MAX_TEXT,
  WORKER_FIELDS,
} from '../lib/events.ts';

/** One UTC day's page views by slug, or its downloaders by slug. */
export type Day = Record<string, number>;

/** Days over which a view's or a download's weight in `recent` halves. */
export const HALF_LIFE_DAYS = 7;
/** How many views one visitor downloading a piece counts for in `recent`. */
export const DOWNLOAD_WEIGHT = 5;

/** A day file's name: `YYYY-MM-DD.json`. */
export const DAY_FILE = /^(\d{4}-\d{2}-\d{2})\.json$/;

const SLUG_PATH = /^\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/;
const RENAME = /^\/([^/\s]+)\s+\/([^/\s]+)\s+301$/;
const DAY_MS = 86_400_000;

/** The slug a page path names (`/loose-squares` or `/loose-squares/`), else undefined. */
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

const COUNT = 'must be a non-negative integer';
const Count = z.int({ error: COUNT }).check(z.minimum(0, { error: COUNT }));

/** `schema`'s parse of `data`; throws naming the first problem and where it is. */
function parse<T>(schema: z.ZodMiniType<T>, data: unknown): T {
  const result = schema.safeParse(data);
  if (result.success) return result.data;
  const [issue] = result.error.issues;
  const where = issue.path.join('.');
  const what =
    issue.code === 'unrecognized_keys' ? `unexpected ${issue.keys.join(', ')}` : issue.message;
  throw new Error(where ? `${where}: ${what}` : what);
}

const DaySchema = z.record(z.string(), Count, { error: 'must be an object of slug: views' });

/** A views day file's JSON as a Day; throws unless it is an object of non-negative integer counts. */
export function parseDay(text: string): Day {
  return parse(DaySchema, JSON.parse(text));
}

export type Cell = string | number | boolean;
/** One event's rows grouped by every column but `n`, the event count weighted by sampling. */
export interface EventTable {
  columns: string[];
  rows: Cell[][];
}
/** One UTC day of product events, as an events day file holds it. */
export interface EventsDay {
  /** Distinct visitor keys that sent any event. */
  visitors: number;
  /** Distinct visitors that exported each slug. */
  downloads: Day;
  export: EventTable;
  theme: EventTable;
  share: EventTable;
}

export const EVENT_NAMES = Object.keys(EVENT_FIELDS) as EventName[];

/** The columns a new day file gets for `event`: its own fields, the context fields and the Worker's but `visitor`, then `n`. */
export function eventColumns(event: EventName): string[] {
  return [
    ...Object.keys(EVENT_FIELDS[event]),
    ...Object.keys(CONTEXT_FIELDS),
    ...Object.keys(WORKER_FIELDS).filter((k) => k !== 'visitor'),
    'n',
  ];
}

/** Any cell, and all a field the model no longer has is checked against. */
const Cell = z.union([z.string().check(z.maxLength(MAX_TEXT)), z.number(), z.boolean()]);
const N = z.int().check(z.minimum(1));

const Table = z
  .strictObject(
    {
      columns: z
        .array(z.string().check(z.regex(/^[a-z]+$/, 'must be a lowercase field name')), {
          error: 'must be a list of field names',
        })
        .check(
          z.refine(
            (c) => c.at(-1) === 'n' && new Set(c).size === c.length,
            'must be distinct field names, n last',
          ),
          z.refine((c) => !c.includes('visitor'), 'must not hold the visitor key'),
        ),
      // Cells are checked below, where a problem is reported by column name.
      rows: z.array(z.array(z.unknown(), { error: 'must be a list of values' }), {
        error: 'must be a list of lists',
      }),
    },
    { error: 'must be an object of columns and rows' },
  )
  .check(
    z.superRefine(({ columns, rows }, ctx) => {
      rows.forEach((row, i) => {
        if (row.length !== columns.length) {
          ctx.addIssue({
            code: 'custom',
            input: row,
            path: ['rows', i],
            message: `must have ${columns.length} values`,
          });
          return;
        }
        columns.forEach((c, j) => {
          const field =
            c === 'n' ? N : Object.hasOwn(FIELDS, c) ? FIELDS[c as keyof typeof FIELDS] : Cell;
          if (!field.safeParse(row[j]).success)
            ctx.addIssue({
              code: 'custom',
              input: row[j],
              path: ['rows', i, c],
              message: 'is out of type or bounds',
            });
        });
      });
    }),
  );

const EventsFile = z.catchall(
  z.object(
    {
      visitors: Count,
      downloads: z.record(z.string(), Count, { error: 'must be an object of slug: visitors' }),
    },
    { error: 'must be an object of visitors, downloads and event tables' },
  ),
  Table,
);

/**
 * An events day file's JSON as an EventsDay. Throws unless `visitors` and `downloads` hold
 * non-negative integer counts and every other key is a table whose columns are distinct lowercase
 * names ending in `n`, without `visitor`. Each cell must be of the type and within the bounds
 * src/lib/events.ts sets for its field, `n` at least 1; a field the model no longer has takes any
 * short text, number or boolean. A file keeps the columns it was written with, and an event the file
 * lacks reads as no rows while one the model no longer has is checked and dropped, so a change to
 * the event model leaves the files already written readable.
 */
export function parseEvents(text: string): EventsDay {
  const { visitors, downloads, ...tables } = parse(EventsFile, JSON.parse(text));
  const events = Object.fromEntries(
    EVENT_NAMES.map((e) => [e, tables[e] ?? { columns: eventColumns(e), rows: [] }]),
  );
  return { visitors, downloads, ...events } as EventsDay;
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

export interface Totals {
  /** Every recorded view. */
  views: number;
  /**
   * Views plus DOWNLOAD_WEIGHT times downloaders, each weighted by 2^(-age / HALF_LIFE_DAYS), age
   * in days before the newest day on record of either kind.
   */
  recent: number;
}

/**
 * Each slug's Totals over `views` and `downloads` (date to Day). A renamed slug counts for the slug
 * it redirects to, following chains; a redirect loop leaves the slugs in it as they are.
 */
export function pieceTotals(
  views: ReadonlyMap<string, Day>,
  downloads: ReadonlyMap<string, Day> = new Map(),
  renamed: ReadonlyMap<string, string> = new Map(),
): Map<string, Totals> {
  const current = (slug: string) => {
    const seen = new Set<string>();
    let s = slug;
    for (let next = renamed.get(s); next !== undefined && !seen.has(s); next = renamed.get(s)) {
      seen.add(s);
      s = next;
    }
    return seen.has(s) ? slug : s;
  };
  const newest = Math.max(...[...views.keys(), ...downloads.keys()].map(dayNumber));
  const out = new Map<string, Totals>();
  const add = (days: ReadonlyMap<string, Day>, weight: number, counted: boolean) => {
    for (const [date, day] of days) {
      const w = weight * 2 ** (-(newest - dayNumber(date)) / HALF_LIFE_DAYS);
      for (const [slug, n] of Object.entries(day)) {
        const key = current(slug);
        const t = out.get(key) ?? { views: 0, recent: 0 };
        if (counted) t.views += n;
        t.recent += n * w;
        out.set(key, t);
      }
    }
  };
  add(views, 1, true);
  add(downloads, DOWNLOAD_WEIGHT, false);
  return out;
}
