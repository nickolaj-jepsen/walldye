/**
 * Writes `<dir>/<YYYY-MM-DD>.json`, walldye.com's product events on a UTC day, for every complete
 * day that Analytics Engine still holds and `dir` has no file for, then rebuilds `<dir>/all.json`
 * from every day file.
 *
 * node scripts/stats/events.ts <dir>
 *
 * Reads CLOUDFLARE_ANALYTICS_TOKEN (Account Analytics Read) and CLOUDFLARE_ACCOUNT_ID.
 *
 * Days run from the oldest file, or with none from the first day that has a row, to yesterday. A day
 * after that with no rows still gets a file, so a missing file means a day that was never fetched.
 * A day file is an EventsDay (src/server/stats.ts), its rows sorted.
 *
 * all.json, for a dashboard that reads one URL, sorted by date:
 *   { "days": [{ "date", "visitors", "downloads" }], "counts": [{ "date", "event", "field", "value", "n" }] }
 * `downloads` sums the day's downloaders over slugs. `counts` holds, per day, event and CHARTED
 * field, the event count `n` of each value, as text (`screen` is `<w>x<h>`); the event `downloads`
 * with field `slug` holds downloaders instead. Past TOP_VALUES values, the rest are summed as
 * `(other)`. That bounds a day to 18 fields of at most TOP_VALUES + 1 rows of about 100 bytes, so
 * about 20 KB a day and 7 MB a year however busy the site is; most fields have only a few values.
 * A field a day file lacks is not counted that day.
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { column, type EventName, FIELDS } from '../../src/lib/events.ts';
import {
  type Cell,
  DAY_FILE,
  type Day,
  dayNumber,
  EVENT_NAMES,
  type EventsDay,
  type EventTable,
  eventColumns,
  isoDay,
  parseEvents,
} from '../../src/server/stats.ts';

/** Production only: Previews write to a dataset of their own. */
export const DATASET = 'walldye_events';
/**
 * Whole days back from today that are safe to read at any hour: Analytics Engine keeps rows for three
 * months, which can be 89 days, so the oldest day read must start less than 89 days ago.
 */
export const HOLD_DAYS = 88;
/** Values kept per day, event and field in all.json. */
export const TOP_VALUES = 10;
export const OTHER = '(other)';
/** The fields all.json counts; `screen` is `w` and `h` joined. */
export const CHARTED: Record<EventName, readonly string[]> = {
  export: [
    'slug',
    'format',
    'size',
    'aspect',
    'version',
    'theme',
    'source',
    'scheme',
    'country',
    'phone',
    'screen',
  ],
  theme: ['kind', 'name', 'via', 'theme'],
  share: ['page', 'theme'],
};

const DAY_S = 86_400;

/** Runs one SQL statement and returns its rows as objects keyed by column name. */
export type Query = (sql: string) => Promise<Record<string, unknown>[]>;

/** A Query against the Analytics Engine SQL API; throws on an HTTP error or a body without data. */
export function sqlApi(account: string, token: string, fetcher: typeof fetch = fetch): Query {
  const url = `https://api.cloudflare.com/client/v4/accounts/${account}/analytics_engine/sql`;
  return async (sql) => {
    const res = await fetcher(url, {
      method: 'POST',
      headers: { authorization: `Bearer ${token}` },
      body: `${sql} FORMAT JSON`,
    });
    const text = await res.text();
    if (!res.ok) throw new Error(`Analytics Engine SQL ${res.status}: ${text.slice(0, 500)}`);
    const body = JSON.parse(text) as { data?: unknown };
    if (!Array.isArray(body.data)) throw new Error(`Analytics Engine SQL: no data in ${text}`);
    return body.data as Record<string, unknown>[];
  };
}

/** A count from a result row; ClickHouse's JSON quotes 64-bit integers. */
function num(v: unknown): number {
  const n = typeof v === 'string' ? Number(v) : v;
  if (typeof n !== 'number' || !Number.isFinite(n)) throw new Error(`not a number: ${String(v)}`);
  return n;
}

/** Rows timestamped from day number `from` up to, not including, day `to`. */
export function between(from: number, to: number): string {
  return `timestamp >= toDateTime(${from * DAY_S}) AND timestamp < toDateTime(${to * DAY_S})`;
}

/** The first day number before `to` and from `from` with a row, or null when there is none. */
export async function firstDay(query: Query, from: number, to: number): Promise<number | null> {
  const [row] = await query(
    `SELECT count() AS n, min(toUnixTimestamp(timestamp)) AS t FROM ${DATASET} WHERE ${between(from, to)}`,
  );
  return row && num(row.n) > 0 ? Math.floor(num(row.t) / DAY_S) : null;
}

/**
 * Day numbers to fetch, oldest first: those from the oldest of `have` (or `first` when `have` is
 * empty) up to yesterday that have no file, and not older than HOLD_DAYS.
 */
export function missingDays(
  have: readonly string[],
  today: number,
  first: number | null,
): number[] {
  const got = new Set(have.map(dayNumber));
  const start = got.size ? Math.min(...got) : first;
  if (start === null) return [];
  const out: number[] = [];
  for (let d = Math.max(start, today - HOLD_DAYS); d < today; d++) if (!got.has(d)) out.push(d);
  return out;
}

/** Row order: column by column, numbers and booleans by value, text by code unit. */
export function compareRows(a: readonly Cell[], b: readonly Cell[]): number {
  for (let i = 0; i < a.length; i++) {
    const x = a[i];
    const y = b[i];
    if (x === y) continue;
    if (typeof x === 'string' && typeof y === 'string') return x < y ? -1 : 1;
    return Number(x) < Number(y) ? -1 : 1;
  }
  return 0;
}

function cell(field: string, v: unknown): Cell {
  if (field === 'n') return num(v);
  switch (FIELDS[field as keyof typeof FIELDS].type) {
    case 'string':
      return String(v);
    case 'boolean':
      return num(v) === 1;
    default:
      return num(v);
  }
}

/** The SQL for one event's grouped rows on day `d`; `LIMIT ALL` is the SQL API's documented no-cap. */
export function tableSql(event: EventName, d: number): string {
  const cols = eventColumns(event)
    .filter((c) => c !== 'n')
    .map(column)
    .join(', ');
  return `SELECT ${cols}, SUM(_sample_interval) AS n FROM ${DATASET} WHERE index1 = '${event}' AND ${between(d, d + 1)} GROUP BY ${cols} LIMIT ALL`;
}

/** Day `d` as an EventsDay, rows sorted, from five queries. */
export async function fetchDay(query: Query, d: number): Promise<EventsDay> {
  const range = between(d, d + 1);
  const visitor = column('visitor');
  const slug = column('slug');
  const [total] = await query(
    `SELECT count(DISTINCT ${visitor}) AS visitors FROM ${DATASET} WHERE ${range}`,
  );
  const downloads: Day = {};
  const exported = await query(
    `SELECT ${slug}, count(DISTINCT ${visitor}) AS visitors FROM ${DATASET} WHERE index1 = 'export' AND ${range} GROUP BY ${slug} LIMIT ALL`,
  );
  for (const row of exported.sort((a, b) => (String(a[slug]) < String(b[slug]) ? -1 : 1)))
    downloads[String(row[slug])] = num(row.visitors);
  const tables = {} as Record<EventName, EventTable>;
  for (const event of EVENT_NAMES) {
    const columns = eventColumns(event);
    const rows = (await query(tableSql(event, d))).map((row) =>
      columns.map((c) => cell(c, row[c === 'n' ? 'n' : column(c)])),
    );
    tables[event] = { columns, rows: rows.sort(compareRows) };
  }
  return { visitors: total ? num(total.visitors) : 0, downloads, ...tables };
}

/** `day` as a day file: two-space indents, a table's columns on one line and each row on its own. */
export function dayJson(day: EventsDay): string {
  const downloads = JSON.stringify(day.downloads, null, 2).replaceAll('\n', '\n  ');
  const table = ({ columns, rows }: EventTable) => {
    const body = rows.length
      ? `[\n      ${rows.map((r) => JSON.stringify(r)).join(',\n      ')}\n    ]`
      : '[]';
    return `{\n    "columns": ${JSON.stringify(columns)},\n    "rows": ${body}\n  }`;
  };
  const events = EVENT_NAMES.map((e) => `  "${e}": ${table(day[e])}`).join(',\n');
  return `{\n  "visitors": ${day.visitors},\n  "downloads": ${downloads},\n${events}\n}\n`;
}

export interface AllDay {
  date: string;
  visitors: number;
  downloads: number;
}
export interface AllCount {
  date: string;
  event: string;
  field: string;
  value: string;
  n: number;
}

/** The TOP_VALUES largest of `counts` by n (ties by value), the rest summed as OTHER. */
function top(counts: Map<string, number>): [string, number][] {
  const sorted = [...counts].sort(([va, a], [vb, b]) => b - a || (va < vb ? -1 : 1));
  if (sorted.length <= TOP_VALUES) return sorted;
  const rest = sorted.slice(TOP_VALUES).reduce((s, [, n]) => s + n, 0);
  return [...sorted.slice(0, TOP_VALUES), [OTHER, rest]];
}

/** all.json's content from day files by date. */
export function buildAll(days: ReadonlyMap<string, EventsDay>): {
  days: AllDay[];
  counts: AllCount[];
} {
  const out = { days: [] as AllDay[], counts: [] as AllCount[] };
  for (const date of [...days.keys()].sort()) {
    const day = days.get(date)!;
    const downloads = Object.values(day.downloads).reduce((s, n) => s + n, 0);
    out.days.push({ date, visitors: day.visitors, downloads });
    const push = (event: string, field: string, counts: Map<string, number>) => {
      for (const [value, n] of top(counts)) out.counts.push({ date, event, field, value, n });
    };
    for (const event of EVENT_NAMES) {
      const { columns, rows } = day[event];
      const at = (c: string) => columns.indexOf(c);
      for (const field of CHARTED[event]) {
        // A day file keeps the columns it was written with, so an older one can lack a field.
        if ((field === 'screen' ? ['w', 'h'] : [field]).some((c) => at(c) < 0)) continue;
        const counts = new Map<string, number>();
        for (const row of rows) {
          const value =
            field === 'screen' ? `${row[at('w')]}x${row[at('h')]}` : String(row[at(field)]);
          counts.set(value, (counts.get(value) ?? 0) + (row[at('n')] as number));
        }
        push(event, field, counts);
      }
    }
    push('downloads', 'slug', new Map(Object.entries(day.downloads)));
  }
  return out;
}

/** buildAll()'s result with one day or count per line. */
export function allJson(days: ReadonlyMap<string, EventsDay>): string {
  const all = buildAll(days);
  const list = (items: object[]) =>
    items.length ? `[\n    ${items.map((i) => JSON.stringify(i)).join(',\n    ')}\n  ]` : '[]';
  return `{\n  "days": ${list(all.days)},\n  "counts": ${list(all.counts)}\n}\n`;
}

/**
 * Writes the missing day files into `dir` as of `now`, then all.json when any day file exists.
 * Returns the dates written. Throws naming a malformed day file.
 */
export async function fetchEvents(dir: string, now: Date, query: Query): Promise<string[]> {
  mkdirSync(dir, { recursive: true });
  const have = readdirSync(dir).flatMap((f) => DAY_FILE.exec(f)?.[1] ?? []);
  const today = Math.floor(now.getTime() / (DAY_S * 1000));
  const first = have.length ? null : await firstDay(query, today - HOLD_DAYS, today);
  const written: string[] = [];
  for (const d of missingDays(have, today, first)) {
    const day = await fetchDay(query, d);
    const text = dayJson(day);
    // What is written must read back.
    parseEvents(text);
    writeFileSync(join(dir, `${isoDay(d)}.json`), text);
    written.push(isoDay(d));
    console.log(`${isoDay(d)}: ${day.visitors} visitors`);
  }
  const days = new Map<string, EventsDay>();
  for (const file of readdirSync(dir).sort()) {
    const date = DAY_FILE.exec(file)?.[1];
    if (!date) continue;
    try {
      days.set(date, parseEvents(readFileSync(join(dir, file), 'utf8')));
    } catch (e) {
      throw new Error(`${join(dir, file)}: ${(e as Error).message}`);
    }
  }
  if (days.size) writeFileSync(join(dir, 'all.json'), allJson(days));
  return written;
}

function env(name: string): string {
  const v = process.env[name]?.trim();
  if (!v) throw new Error(`${name} is not set`);
  return v;
}

async function main(dir: string | undefined): Promise<void> {
  if (!dir) throw new Error('usage: node scripts/stats/events.ts <dir>');
  const query = sqlApi(env('CLOUDFLARE_ACCOUNT_ID'), env('CLOUDFLARE_ANALYTICS_TOKEN'));
  const written = await fetchEvents(dir, new Date(), query);
  if (!written.length) console.log('nothing to fetch');
}

if (import.meta.main) {
  main(process.argv[2]).catch((e: Error) => {
    console.error(e.message);
    process.exit(1);
  });
}
