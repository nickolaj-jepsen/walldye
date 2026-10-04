import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  buildAll,
  CHARTED,
  dayJson,
  fetchEvents,
  HOLD_DAYS,
  OTHER,
  sqlApi,
  TOP_VALUES,
} from '../../scripts/stats/events';
import { BLOBS, column, DOUBLES, encodeEvent, type StoredEvent } from '../../src/lib/events';
import {
  dayNumber,
  type EventsDay,
  eventColumns,
  isoDay,
  parseEvents,
} from '../../src/server/stats';

const CONTEXT = {
  page: 'loose-squares',
  w: 2560,
  h: 1440,
  dpr: 2,
  phone: false,
  scheme: 'dark',
  theme: 'nord',
  token: 'nord',
  source: 'saved',
  country: 'DK',
};

const exp = (visitor: string, slug: string, extra: Partial<StoredEvent> = {}): StoredEvent =>
  ({
    event: 'export',
    slug,
    version: 'default',
    format: 'png',
    aspect: '16:9',
    size: '2560x1440',
    first: true,
    ...CONTEXT,
    visitor,
    ...extra,
  }) as StoredEvent;
const theme = (visitor: string): StoredEvent => ({
  event: 'theme',
  kind: 'preset',
  name: 'nord',
  via: 'index',
  ...CONTEXT,
  visitor,
});
const share = (visitor: string): StoredEvent => ({
  event: 'share',
  ...CONTEXT,
  phone: true,
  visitor,
});

interface Row {
  /** Seconds since the epoch. */
  at: number;
  sample: number;
  event: StoredEvent;
}

const at = (date: string, hour = 12) => dayNumber(date) * 86_400 + hour * 3600;

/**
 * A stand-in for the SQL API that answers the statements scripts/stats/events.ts sends from `rows`,
 * stored as encodeEvent() stores them; answers in `order` so callers can't rely on it.
 */
function fakeApi(rows: Row[], order: 'asc' | 'desc' = 'asc') {
  const sent: string[] = [];
  const auth: (string | null)[] = [];
  const fetcher = (async (_url: string, init: RequestInit) => {
    const sql = String(init.body);
    sent.push(sql);
    auth.push(new Headers(init.headers).get('authorization'));
    expect(sql.endsWith(' FORMAT JSON')).toBe(true);
    const range = /timestamp >= toDateTime\((\d+)\) AND timestamp < toDateTime\((\d+)\)/.exec(sql);
    if (!range) throw new Error(`no time range in ${sql}`);
    const index = /index1 = '(\w+)'/.exec(sql)?.[1];
    const hits = rows
      .filter((r) => r.at >= Number(range[1]) && r.at < Number(range[2]))
      .filter((r) => !index || r.event.event === index)
      .map((r) => {
        const p = encodeEvent(r.event);
        const cols: Record<string, unknown> = { _sample_interval: r.sample };
        BLOBS.forEach((_, i) => {
          cols[`blob${i + 1}`] = p.blobs[i];
        });
        DOUBLES.forEach((_, i) => {
          cols[`double${i + 1}`] = p.doubles[i];
        });
        return { at: r.at, cols };
      });
    let data: Record<string, unknown>[];
    const visitor = column('visitor');
    if (sql.startsWith('SELECT count() AS n')) {
      data = [{ n: String(hits.length), t: hits.length ? Math.min(...hits.map((h) => h.at)) : 0 }];
    } else if (!sql.includes('GROUP BY')) {
      data = [{ visitors: String(new Set(hits.map((h) => h.cols[visitor])).size) }];
    } else {
      const groupBy = sql.replace(' LIMIT ALL FORMAT JSON', '').split('GROUP BY ')[1].split(', ');
      const groups = new Map<
        string,
        { key: Record<string, unknown>; v: Set<unknown>; n: number }
      >();
      for (const h of hits) {
        const key = Object.fromEntries(groupBy.map((c) => [c, h.cols[c]]));
        const id = JSON.stringify(key);
        const g = groups.get(id) ?? { key, v: new Set(), n: 0 };
        g.v.add(h.cols[visitor]);
        g.n += h.cols._sample_interval as number;
        groups.set(id, g);
      }
      data = [...groups.values()].map((g) =>
        sql.includes('AS visitors')
          ? { ...g.key, visitors: String(g.v.size) }
          : { ...g.key, n: String(g.n) },
      );
    }
    if (order === 'desc') data.reverse();
    return new Response(JSON.stringify({ meta: [], data, rows: data.length }));
  }) as typeof fetch;
  return { fetcher, sent, auth, query: sqlApi('acct', 'tok', fetcher) };
}

const ROWS: Row[] = [
  { at: at('2026-09-20'), sample: 1, event: exp('v1', 'loose-squares') },
  { at: at('2026-09-20', 13), sample: 2, event: exp('v1', 'loose-squares') },
  { at: at('2026-09-20', 14), sample: 1, event: exp('v2', 'loose-squares', { format: 'svg' }) },
  { at: at('2026-09-20', 15), sample: 1, event: exp('v2', 'dither-moon', { first: false }) },
  { at: at('2026-09-20', 16), sample: 1, event: theme('v3') },
  { at: at('2026-09-22', 1), sample: 1, event: share('v4') },
  // Today's rows are left for tomorrow's run.
  { at: at('2026-09-23', 1), sample: 1, event: share('v5') },
];
const NOW = new Date(`2026-09-23T02:23:00Z`);

const dirs: string[] = [];
const tmp = () => {
  const d = mkdtempSync(join(tmpdir(), 'walldye-events-'));
  dirs.push(d);
  return d;
};
beforeEach(() => {
  vi.spyOn(console, 'log').mockImplementation(() => {});
});
afterEach(() => {
  vi.restoreAllMocks();
  for (const d of dirs.splice(0)) rmSync(d, { recursive: true, force: true });
});
const read = (dir: string, file: string) => readFileSync(join(dir, file), 'utf8');

describe('fetchEvents', () => {
  it('starts at the first day with a row and writes every complete day after it', async () => {
    const dir = tmp();
    const api = fakeApi(ROWS);
    expect(await fetchEvents(dir, NOW, api.query)).toEqual([
      '2026-09-20',
      '2026-09-21',
      '2026-09-22',
    ]);
    expect(readdirSync(dir).sort()).toEqual([
      '2026-09-20.json',
      '2026-09-21.json',
      '2026-09-22.json',
      'all.json',
    ]);
    expect(parseEvents(read(dir, '2026-09-21.json'))).toEqual({
      visitors: 0,
      downloads: {},
      export: { columns: eventColumns('export'), rows: [] },
      theme: { columns: eventColumns('theme'), rows: [] },
      share: { columns: eventColumns('share'), rows: [] },
    });
    expect(api.auth.every((a) => a === 'Bearer tok')).toBe(true);
  });

  it('asks for the first row within the days still held, then five statements per day', async () => {
    const api = fakeApi(ROWS);
    await fetchEvents(tmp(), NOW, api.query);
    const today = dayNumber('2026-09-23');
    expect(api.sent[0]).toContain(
      `FROM walldye_events WHERE timestamp >= toDateTime(${(today - HOLD_DAYS) * 86_400}) AND timestamp < toDateTime(${today * 86_400})`,
    );
    const perDay = api.sent.slice(1);
    expect(perDay).toHaveLength(3 * 5);
    for (const [i, date] of ['2026-09-20', '2026-09-21', '2026-09-22'].entries()) {
      const d = dayNumber(date) * 86_400;
      const range = `timestamp >= toDateTime(${d}) AND timestamp < toDateTime(${d + 86_400})`;
      const day = perDay.slice(i * 5, i * 5 + 5);
      expect(day.every((s) => s.includes(range) && s.includes('FROM walldye_events '))).toBe(true);
      expect(day.filter((s) => s.includes('SUM(_sample_interval) AS n'))).toHaveLength(3);
      for (const s of day) expect(s).not.toMatch(/\bAS (?!n\b|visitors\b)/);
      for (const s of day.filter((s) => s.includes('GROUP BY')))
        expect(s.endsWith(' LIMIT ALL FORMAT JSON'), s).toBe(true);
    }
  });

  it('decodes the rows by the layout in src/lib/events.ts, keeping visitor keys out', async () => {
    const dir = tmp();
    await fetchEvents(dir, NOW, fakeApi(ROWS).query);
    const text = read(dir, '2026-09-20.json');
    expect(text).not.toMatch(/"v\d"/);
    const day = parseEvents(text);
    expect(day.visitors).toBe(3);
    expect(day.downloads).toEqual({ 'dither-moon': 1, 'loose-squares': 2 });
    const cols = day.export.columns;
    const row = (e: StoredEvent, n: number) =>
      cols.map((c) => (c === 'n' ? n : (e as unknown as Record<string, unknown>)[c]));
    expect(day.export.rows).toEqual([
      row(exp('', 'dither-moon', { first: false }), 1),
      row(exp('', 'loose-squares'), 3),
      row(exp('', 'loose-squares', { format: 'svg' }), 1),
    ]);
    expect(day.theme.rows).toHaveLength(1);
    expect(day.share.rows).toEqual([]);
  });

  it('writes the same bytes whatever order the API answers in, and a rerun changes nothing', async () => {
    const a = tmp();
    const b = tmp();
    await fetchEvents(a, NOW, fakeApi(ROWS).query);
    await fetchEvents(b, NOW, fakeApi(ROWS, 'desc').query);
    for (const f of readdirSync(a)) expect(read(b, f), f).toBe(read(a, f));
    const before = read(a, 'all.json');
    const again = fakeApi(ROWS);
    expect(await fetchEvents(a, NOW, again.query)).toEqual([]);
    expect(again.sent).toEqual([]);
    expect(read(a, 'all.json')).toBe(before);
  });

  it('fills only the missing days from the oldest file on, within the days still held', async () => {
    const dir = tmp();
    const empty = dayJson(parseEvents(read(await seed(), '2026-09-21.json')));
    writeFileSync(join(dir, '2026-09-19.json'), empty);
    writeFileSync(join(dir, '2026-09-21.json'), empty);
    expect(await fetchEvents(dir, NOW, fakeApi(ROWS).query)).toEqual(['2026-09-20', '2026-09-22']);

    const old = tmp();
    writeFileSync(join(old, '2026-01-01.json'), empty);
    const written = await fetchEvents(old, NOW, fakeApi(ROWS).query);
    expect(written[0]).toBe(isoDay(dayNumber('2026-09-23') - HOLD_DAYS));
    expect(written.at(-1)).toBe('2026-09-22');
  });

  it('reads back no further than a day that started under 89 days ago, the shortest three months', () => {
    const lastRun = (dayNumber('2026-05-01') + 1) * 86_400_000 - 1;
    const oldest = (dayNumber('2026-05-01') - HOLD_DAYS) * 86_400_000;
    expect(lastRun - oldest).toBeLessThan(89 * 86_400_000);
  });

  it('writes nothing while the dataset is empty', async () => {
    const dir = tmp();
    const api = fakeApi([]);
    expect(await fetchEvents(dir, NOW, api.query)).toEqual([]);
    expect(api.sent).toHaveLength(1);
    expect(readdirSync(dir)).toEqual([]);
  });

  it('names a malformed day file', async () => {
    const dir = tmp();
    writeFileSync(join(dir, '2026-09-22.json'), '{}');
    await expect(fetchEvents(dir, NOW, fakeApi([]).query)).rejects.toThrow('2026-09-22.json');
  });

  async function seed(): Promise<string> {
    const dir = tmp();
    await fetchEvents(dir, NOW, fakeApi(ROWS).query);
    return dir;
  }
});

describe('all.json', () => {
  it('rebuilds a day and count list from every day file', async () => {
    const dir = tmp();
    await fetchEvents(dir, NOW, fakeApi(ROWS).query);
    const all = JSON.parse(read(dir, 'all.json'));
    expect(all.days).toEqual([
      { date: '2026-09-20', visitors: 3, downloads: 3 },
      { date: '2026-09-21', visitors: 0, downloads: 0 },
      { date: '2026-09-22', visitors: 1, downloads: 0 },
    ]);
    const on = (event: string, field: string) =>
      all.counts
        .filter((c: { date: string }) => c.date === '2026-09-20')
        .filter((c: { event: string; field: string }) => c.event === event && c.field === field)
        .map(({ value, n }: { value: string; n: number }) => [value, n]);
    expect(on('export', 'format')).toEqual([
      ['png', 4],
      ['svg', 1],
    ]);
    expect(on('export', 'screen')).toEqual([['2560x1440', 5]]);
    expect(on('export', 'phone')).toEqual([['false', 5]]);
    expect(on('downloads', 'slug')).toEqual([
      ['loose-squares', 2],
      ['dither-moon', 1],
    ]);
    expect(on('theme', 'kind')).toEqual([['preset', 1]]);
    const fields = new Set(
      all.counts.map((c: { event: string; field: string }) => `${c.event}.${c.field}`),
    );
    for (const [event, list] of Object.entries(CHARTED))
      for (const f of list) expect(fields.has(`${event}.${f}`), `${event}.${f}`).toBe(true);
  });

  it('keeps the largest values of a field and sums the rest', () => {
    const slugs = Array.from(
      { length: TOP_VALUES + 5 },
      (_, i) => `s${String(i).padStart(2, '0')}`,
    );
    const day: EventsDay = {
      visitors: 1,
      downloads: Object.fromEntries(slugs.map((s, i) => [s, i + 1])),
      export: { columns: eventColumns('export'), rows: [] },
      theme: { columns: eventColumns('theme'), rows: [] },
      share: { columns: eventColumns('share'), rows: [] },
    };
    const counts = buildAll(new Map([['2026-09-20', day]])).counts.filter(
      (c) => c.event === 'downloads',
    );
    expect(counts).toHaveLength(TOP_VALUES + 1);
    expect(counts[0]).toMatchObject({ value: slugs.at(-1), n: slugs.length });
    expect(counts.at(-1)).toEqual({
      date: '2026-09-20',
      event: 'downloads',
      field: 'slug',
      value: OTHER,
      n: 1 + 2 + 3 + 4 + 5,
    });
  });
});

describe('all.json from older day files', () => {
  it('counts only the fields a day file has', () => {
    const columns = ['slug', 'format', 'retired', 'n'];
    const day: EventsDay = {
      visitors: 1,
      downloads: {},
      export: { columns, rows: [['loose-squares', 'png', 'x', 2]] },
      theme: { columns: ['n'], rows: [] },
      share: { columns: ['n'], rows: [] },
    };
    const fields = buildAll(new Map([['2026-09-20', day]])).counts.map(
      (c) => `${c.event}.${c.field}`,
    );
    expect(fields).toEqual(['export.slug', 'export.format']);
  });
});

describe('sqlApi', () => {
  const answer = (status: number, body: unknown) =>
    (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;

  it('posts the statement to the account endpoint with the token', async () => {
    let seen: [string, RequestInit] | undefined;
    const fetcher = (async (url: string, init: RequestInit) => {
      seen = [url, init];
      return new Response('{"data":[{"x":1}]}');
    }) as typeof fetch;
    expect(await sqlApi('acct', 'tok', fetcher)('SELECT 1 AS x')).toEqual([{ x: 1 }]);
    expect(seen?.[0]).toBe(
      'https://api.cloudflare.com/client/v4/accounts/acct/analytics_engine/sql',
    );
    expect(seen?.[1].method).toBe('POST');
    expect(seen?.[1].body).toBe('SELECT 1 AS x FORMAT JSON');
  });

  it('throws on an error or a body without data', async () => {
    await expect(sqlApi('a', 't', answer(400, { errors: ['bad'] }))('SELECT 1')).rejects.toThrow(
      '400',
    );
    await expect(sqlApi('a', 't', answer(200, {}))('SELECT 1')).rejects.toThrow('no data');
  });
});

describe('column', () => {
  it('names the blob or double that holds a field, 1-based', () => {
    expect(column(BLOBS[0])).toBe('blob1');
    expect(column('format')).toBe(`blob${BLOBS.indexOf('format') + 1}`);
    expect(column('first')).toBe(`double${DOUBLES.indexOf('first') + 1}`);
    expect(() => column('event')).toThrow();
  });
});
