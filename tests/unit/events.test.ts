import { describe, expect, it } from 'vitest';
import {
  BLOBS,
  type ClientEvent,
  CONTEXT_FIELDS,
  DOUBLES,
  decodeEvent,
  EVENT_FIELDS,
  encodeEvent,
  MAX_TEXT,
  parseEvent,
  type StoredEvent,
  validateEvent,
  WORKER_FIELDS,
} from '../../src/lib/events';

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
};

const VALID: ClientEvent[] = [
  {
    event: 'export',
    slug: 'loose-squares',
    version: 'default',
    format: 'png',
    aspect: '16:9',
    size: '2560x1440',
    first: true,
    ...CONTEXT,
  },
  {
    event: 'export',
    slug: 'dither-moon',
    version: 'late',
    format: 'svg',
    aspect: '9:19.5',
    size: 'svg',
    first: false,
    ...CONTEXT,
  },
  { event: 'theme', kind: 'preset', name: 'nord', via: 'index', ...CONTEXT },
  {
    event: 'theme',
    kind: 'custom',
    name: 'custom',
    via: 'hex',
    ...CONTEXT,
    theme: 'custom',
    token: '112233-ddeeff-ff8800',
  },
  { event: 'share', ...CONTEXT, page: '404', phone: true, dpr: 2.625, source: 'shared' },
];

describe('validateEvent', () => {
  it('accepts every event shape as sent', () => {
    for (const e of VALID) expect(validateEvent(e)).toEqual(e);
  });

  it('drops fields the event does not have', () => {
    expect(validateEvent({ ...VALID[4], slug: 'x', extra: 1 })).toEqual(VALID[4]);
  });

  it('rejects what is not an object or names no known event', () => {
    for (const bad of [null, 1, 'share', [VALID[4]], {}, { ...VALID[4], event: 'view' }])
      expect(validateEvent(bad)).toBeNull();
    expect(validateEvent({ ...VALID[4], event: 'constructor' })).toBeNull();
  });

  it('rejects a missing field', () => {
    for (const e of VALID) {
      for (const key of Object.keys(e)) {
        if (key === 'event') continue;
        const { [key]: _, ...rest } = e as unknown as Record<string, unknown>;
        expect(validateEvent(rest), `${e.event} without ${key}`).toBeNull();
      }
    }
  });

  it('rejects fields of the wrong type or out of bounds', () => {
    const base = VALID[0];
    const cases: Record<string, unknown>[] = [
      { slug: 1 },
      { slug: 'x'.repeat(MAX_TEXT + 1) },
      { first: 'true' },
      { first: 1 },
      { w: -1 },
      { w: 1.5 },
      { h: 1e9 },
      { w: '2560' },
      { dpr: 0 },
      { dpr: Number.NaN },
      { dpr: Number.POSITIVE_INFINITY },
      { dpr: 100 },
      { phone: null },
      { token: { a: 1 } },
    ];
    for (const patch of cases) expect(validateEvent({ ...base, ...patch })).toBeNull();
    expect(validateEvent({ ...base, slug: 'x'.repeat(MAX_TEXT) })).not.toBeNull();
  });
});

describe('parseEvent', () => {
  it('parses JSON and rejects what does not parse', () => {
    expect(parseEvent(JSON.stringify(VALID[2]))).toEqual(VALID[2]);
    for (const bad of ['', '{', 'null', '[]', '"share"']) expect(parseEvent(bad)).toBeNull();
  });
});

describe('row layout', () => {
  it('has one column per field, within the Analytics Engine limits', () => {
    const fields = new Set([
      ...Object.keys(CONTEXT_FIELDS),
      ...Object.keys(WORKER_FIELDS),
      ...Object.values(EVENT_FIELDS).flatMap((f) => Object.keys(f)),
    ]);
    const columns = [...BLOBS, ...DOUBLES];
    expect(new Set(columns).size).toBe(columns.length);
    expect(new Set(columns)).toEqual(fields);
    expect(BLOBS.length).toBeLessThanOrEqual(20);
    expect(DOUBLES.length).toBeLessThanOrEqual(20);
    for (const name of Object.keys(EVENT_FIELDS))
      expect(new TextEncoder().encode(name).length).toBeLessThanOrEqual(96);
  });

  it('keeps the stored column order', () => {
    // Stored rows are decoded by position, so this list only ever grows at the end.
    expect(BLOBS).toEqual([
      'page',
      'scheme',
      'theme',
      'token',
      'source',
      'visitor',
      'country',
      'slug',
      'version',
      'format',
      'aspect',
      'size',
      'kind',
      'name',
      'via',
    ]);
    expect(DOUBLES).toEqual(['w', 'h', 'dpr', 'phone', 'first']);
  });

  it('round-trips every event through a row', () => {
    for (const e of VALID) {
      const stored: StoredEvent = { ...e, visitor: '0123456789abcdef', country: 'DK' };
      const row = encodeEvent(stored);
      expect(row.indexes).toEqual([e.event]);
      expect(row.blobs).toHaveLength(BLOBS.length);
      expect(row.doubles).toHaveLength(DOUBLES.length);
      expect(decodeEvent(row.indexes[0], row.blobs, row.doubles)).toEqual(stored);
    }
  });

  it('leaves fields an event lacks empty and stores booleans as 0 or 1', () => {
    const row = encodeEvent({ ...VALID[4], visitor: 'v', country: '' });
    expect(row.blobs[BLOBS.indexOf('slug')]).toBe('');
    expect(row.doubles[DOUBLES.indexOf('first')]).toBe(0);
    expect(row.doubles[DOUBLES.indexOf('phone')]).toBe(1);
    expect(decodeEvent('view', row.blobs, row.doubles)).toBeNull();
  });
});
