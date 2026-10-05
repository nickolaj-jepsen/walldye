import { describe, expect, it } from 'vitest';
import { chunks, dayJson, daysToFetch, type Row, toDays } from '../../scripts/stats/views';
import {
  type Day,
  DOWNLOAD_WEIGHT,
  dayNumber,
  eventColumns,
  HALF_LIFE_DAYS,
  isoDay,
  parseDay,
  parseEvents,
  pathSlug,
  pieceTotals,
  renames,
} from '../../src/server/stats';

const row = (date: string, requestPath: string, count: number): Row => ({
  count,
  dimensions: { date, requestPath },
});

describe('pathSlug', () => {
  it('reads a slug from a one-segment path, trailing slash or not', () => {
    expect(['/loose-squares', '/loose-squares/', '/dither-moon'].map(pathSlug)).toEqual([
      'loose-squares',
      'loose-squares',
      'dither-moon',
    ]);
  });

  it('drops everything else', () => {
    for (const path of [
      '/',
      '/t/abc.svg',
      '/wp-login.php',
      '/Schotter',
      '/a--b',
      '/-a',
      '/.env',
      'loose-squares',
    ]) {
      expect(pathSlug(path), path).toBeUndefined();
    }
  });
});

describe('days', () => {
  it('round-trips ISO dates through day numbers', () => {
    expect(isoDay(dayNumber('2026-09-27'))).toBe('2026-09-27');
    expect(dayNumber('2026-09-28') - dayNumber('2026-09-27')).toBe(1);
  });

  it('parses a day file and rejects anything but counts', () => {
    expect(parseDay('{"loose-squares": 3}')).toEqual({ 'loose-squares': 3 });
    for (const text of ['[]', 'null', '{"a": -1}', '{"a": 1.5}', '{"a": "2"}'])
      expect(() => parseDay(text), text).toThrow();
  });
});

describe('renames', () => {
  it('reads the 301 lines of _redirects and skips comments', () => {
    const text =
      '# Renamed wallpapers, one per line: /<old-slug> /<new-slug> 301\n/moon /dither-moon 301\n/x /y 302\n';
    expect([...renames(text)]).toEqual([['moon', 'dither-moon']]);
  });
});

describe('pieceTotals', () => {
  it('totals every view and halves a day each half-life before the newest', () => {
    const days = new Map<string, Day>([
      ['2026-09-27', { a: 4, b: 1 }],
      [isoDay(dayNumber('2026-09-27') - HALF_LIFE_DAYS), { a: 8 }],
      [isoDay(dayNumber('2026-09-27') - 2 * HALF_LIFE_DAYS), { c: 40 }],
    ]);
    const t = pieceTotals(days);
    expect(t.get('a')).toEqual({ views: 12, recent: 8 });
    expect(t.get('b')).toEqual({ views: 1, recent: 1 });
    expect(t.get('c')).toEqual({ views: 40, recent: 10 });
  });

  it('counts a renamed slug for the one it now goes by, through chains, and leaves loops alone', () => {
    const days = new Map<string, Day>([['2026-09-27', { old: 1, older: 2, now: 3, p: 5, q: 7 }]]);
    const t = pieceTotals(
      days,
      new Map(),
      new Map([
        ['older', 'old'],
        ['old', 'now'],
        ['p', 'q'],
        ['q', 'p'],
      ]),
    );
    expect(t.get('now')?.views).toBe(6);
    expect(t.has('old')).toBe(false);
    expect([t.get('p')?.views, t.get('q')?.views]).toEqual([5, 7]);
  });

  it('is empty without days', () => {
    expect(pieceTotals(new Map()).size).toBe(0);
  });

  it('adds downloaders to recent at DOWNLOAD_WEIGHT, halving the same way, and leaves views alone', () => {
    const d = dayNumber('2026-09-27');
    const views = new Map<string, Day>([['2026-09-27', { a: 4 }]]);
    const downloads = new Map<string, Day>([
      ['2026-09-27', { a: 1, b: 2 }],
      [isoDay(d - HALF_LIFE_DAYS), { b: 4 }],
    ]);
    const t = pieceTotals(views, downloads);
    expect(t.get('a')).toEqual({ views: 4, recent: 4 + DOWNLOAD_WEIGHT });
    expect(t.get('b')).toEqual({ views: 0, recent: DOWNLOAD_WEIGHT * (2 + 4 / 2) });
  });

  it('measures age from the newest day of either kind', () => {
    const d = dayNumber('2026-09-27');
    const views = new Map<string, Day>([[isoDay(d - HALF_LIFE_DAYS), { a: 8 }]]);
    const downloads = new Map<string, Day>([['2026-09-27', { b: 1 }]]);
    expect(pieceTotals(views, downloads).get('a')).toEqual({ views: 8, recent: 4 });
    const later = new Map<string, Day>([[isoDay(d + HALF_LIFE_DAYS), {}]]);
    expect(pieceTotals(later, downloads).get('b')?.recent).toBe(DOWNLOAD_WEIGHT / 2);
  });

  it('folds renamed slugs in downloads as in views', () => {
    const t = pieceTotals(
      new Map([['2026-09-27', { now: 1 }]]),
      new Map([['2026-09-27', { old: 2 }]]),
      new Map([['old', 'now']]),
    );
    expect(t.get('now')).toEqual({ views: 1, recent: 1 + 2 * DOWNLOAD_WEIGHT });
    expect(t.has('old')).toBe(false);
  });
});

describe('parseEvents', () => {
  const exportRow = [
    'loose-squares',
    'default',
    'png',
    '16:9',
    'screen',
    true,
    'loose-squares',
    2560,
    1440,
    1.5,
    false,
    'dark',
    'nord',
    'abc',
    'saved',
    'DK',
    3,
  ];
  const valid = () => ({
    visitors: 2,
    downloads: { 'loose-squares': 1 },
    export: { columns: eventColumns('export'), rows: [exportRow] },
    theme: { columns: eventColumns('theme'), rows: [] },
    share: { columns: eventColumns('share'), rows: [] },
  });
  const text = (v: unknown) => JSON.stringify(v);

  it('lists each event table with its fields, the context and country, then n', () => {
    expect(eventColumns('share')).toEqual([
      'page',
      'w',
      'h',
      'dpr',
      'phone',
      'scheme',
      'theme',
      'token',
      'source',
      'country',
      'n',
    ]);
    expect(eventColumns('export').slice(0, 6)).toEqual([
      'slug',
      'version',
      'format',
      'aspect',
      'size',
      'first',
    ]);
    expect(eventColumns('theme')).not.toContain('visitor');
  });

  it('accepts a day file', () => {
    expect(parseEvents(text(valid()))).toEqual(valid());
  });

  it('accepts the columns an older or newer layout wrote', () => {
    const v = valid();
    const older = {
      ...v,
      share: { columns: ['retired', 'page', 'n'], rows: [[3, 'index', 1]] },
      theme: { columns: ['n'], rows: [[2]] },
    };
    expect(parseEvents(text(older))).toEqual(older);
  });

  it('reads an event the file lacks as no rows and drops one the model no longer has', () => {
    const { share: _, ...v } = valid();
    const retired = { columns: ['page', 'n'], rows: [['index', 1]] };
    expect(parseEvents(text({ ...v, retired }))).toEqual(valid());
  });

  it('rejects anything else', () => {
    const bad: [string, (v: ReturnType<typeof valid>) => unknown][] = [
      ['not an object', () => []],
      ['extra key not a table', (v) => ({ ...v, extra: 1 })],
      [
        'retired table with a visitor column',
        (v) => ({ ...v, old: { columns: ['visitor', 'n'], rows: [] } }),
      ],
      ['negative visitors', (v) => ({ ...v, visitors: -1 })],
      ['fractional download', (v) => ({ ...v, downloads: { a: 1.5 } })],
      [
        'n not last',
        (v) => ({ ...v, theme: { columns: [...v.theme.columns].reverse(), rows: [] } }),
      ],
      ['column twice', (v) => ({ ...v, share: { columns: ['page', 'page', 'n'], rows: [] } })],
      ['column not a name', (v) => ({ ...v, share: { columns: ['Page', 'n'], rows: [] } })],
      [
        'unknown column not a scalar',
        (v) => ({ ...v, share: { columns: ['retired', 'n'], rows: [[{}, 1]] } }),
      ],
      [
        'visitor column',
        (v) => ({ ...v, share: { columns: ['visitor', ...v.share.columns], rows: [] } }),
      ],
      ['short row', (v) => ({ ...v, export: { ...v.export, rows: [exportRow.slice(1)] } })],
      ['flag as 0/1', (v) => ({ ...v, export: { ...v.export, rows: [exportRow.with(5, 1)] } })],
      ['zero n', (v) => ({ ...v, export: { ...v.export, rows: [exportRow.with(-1, 0)] } })],
      [
        'text too long',
        (v) => ({ ...v, export: { ...v.export, rows: [exportRow.with(0, 'x'.repeat(65))] } }),
      ],
      [
        'fractional pixels',
        (v) => ({ ...v, export: { ...v.export, rows: [exportRow.with(7, 1.5)] } }),
      ],
      ['rows not a list', (v) => ({ ...v, theme: { ...v.theme, rows: {} } })],
    ];
    for (const [name, change] of bad)
      expect(() => parseEvents(text(change(valid()))), name).toThrow();
  });
});

describe('fetch helpers', () => {
  const now = new Date('2026-09-28T02:23:00Z');
  const week = 7 * 86_400;

  it('fetches from the day after the newest file up to yesterday', () => {
    expect(daysToFetch(['2026-09-20', '2026-09-25'], now, week).map(isoDay)).toEqual([
      '2026-09-26',
      '2026-09-27',
    ]);
    expect(daysToFetch(['2026-09-27'], now, week)).toEqual([]);
  });

  it('starts at the oldest whole day the dataset still holds', () => {
    expect(daysToFetch([], now, week).map(isoDay)).toEqual([
      '2026-09-22',
      '2026-09-23',
      '2026-09-24',
      '2026-09-25',
      '2026-09-26',
      '2026-09-27',
    ]);
    expect(daysToFetch(['2026-01-01'], now, 2 * 86_400).map(isoDay)).toEqual(['2026-09-27']);
  });

  it('splits into consecutive runs no longer than the limit', () => {
    expect(chunks([1, 2, 3, 4, 5, 9, 10], 2)).toEqual([[1, 2], [3, 4], [5], [9, 10]]);
  });

  it('groups rows into days, merging trailing slashes and dropping other paths', () => {
    const days = ['2026-09-26', '2026-09-27'].map(dayNumber);
    const rows = [
      row('2026-09-26', '/a', 2),
      row('2026-09-26', '/a/', 1),
      row('2026-09-26', '/', 50),
      row('2026-09-27', '/t/x.svg', 9),
    ];
    expect([...toDays(rows, days, false)]).toEqual([
      ['2026-09-26', { a: 3 }],
      ['2026-09-27', {}],
    ]);
  });

  it('leaves out the days before the first view when starting fresh', () => {
    const days = ['2026-09-25', '2026-09-26', '2026-09-27'].map(dayNumber);
    expect([...toDays([row('2026-09-26', '/a', 1)], days, true).keys()]).toEqual([
      '2026-09-26',
      '2026-09-27',
    ]);
    expect(toDays([], days, true).size).toBe(0);
    expect(toDays([], days, false).size).toBe(3);
  });

  it('writes a day with sorted slugs', () => {
    expect(dayJson({ b: 1, a: 2 })).toBe('{\n  "a": 2,\n  "b": 1\n}\n');
  });
});
