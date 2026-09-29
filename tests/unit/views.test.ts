import { describe, expect, it } from 'vitest';
import { chunks, dayJson, daysToFetch, type Row, toDays } from '../../scripts/views/fetch';
import {
  type Day,
  dayNumber,
  HALF_LIFE_DAYS,
  isoDay,
  parseDay,
  pathSlug,
  renames,
  viewTotals,
} from '../../src/lib/views';

const row = (date: string, requestPath: string, count: number): Row => ({
  count,
  dimensions: { date, requestPath },
});

describe('pathSlug', () => {
  it('reads a slug from a one-segment path, trailing slash or not', () => {
    expect(['/schotter', '/schotter/', '/dither-moon'].map(pathSlug)).toEqual([
      'schotter',
      'schotter',
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
      'schotter',
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
    expect(parseDay('{"schotter": 3}')).toEqual({ schotter: 3 });
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

describe('viewTotals', () => {
  it('totals every view and halves a day each half-life before the newest', () => {
    const days = new Map<string, Day>([
      ['2026-09-27', { a: 4, b: 1 }],
      [isoDay(dayNumber('2026-09-27') - HALF_LIFE_DAYS), { a: 8 }],
      [isoDay(dayNumber('2026-09-27') - 2 * HALF_LIFE_DAYS), { c: 40 }],
    ]);
    const t = viewTotals(days);
    expect(t.get('a')).toEqual({ views: 12, recent: 8 });
    expect(t.get('b')).toEqual({ views: 1, recent: 1 });
    expect(t.get('c')).toEqual({ views: 40, recent: 10 });
  });

  it('counts a renamed slug for the one it now goes by, through chains, and leaves loops alone', () => {
    const days = new Map<string, Day>([['2026-09-27', { old: 1, older: 2, now: 3, p: 5, q: 7 }]]);
    const t = viewTotals(
      days,
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
    expect(viewTotals(new Map()).size).toBe(0);
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
