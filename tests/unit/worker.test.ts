import { afterEach, describe, expect, it, vi } from 'vitest';
import { BLOBS, MAX_BODY } from '../../src/lib/events';
import { type Env, handle, visitorKey } from '../../src/worker/handle';

const SITE = 'https://walldye.com';
const IP = '203.0.113.7';
const UA = 'Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0';
const DAY = new Date('2026-10-04T12:00:00Z');

const BODY = {
  event: 'export',
  slug: 'loose-squares',
  version: 'default',
  format: 'png',
  aspect: '16:9',
  size: 'screen',
  first: true,
  page: 'loose-squares',
  w: 2560,
  h: 1440,
  dpr: 1,
  phone: false,
  scheme: 'light',
  theme: 'custom',
  token: '112233-ddeeff-ff8800',
  source: 'saved',
};

function fakeEnv(key: string | null = 'secret') {
  const points: { indexes: string[]; blobs: string[]; doubles: number[] }[] = [];
  const assets: Request[] = [];
  const env: Env = {
    ASSETS: {
      fetch: async (r) => {
        assets.push(r);
        return new Response('asset', { status: 200 });
      },
    },
    EVENTS: { writeDataPoint: (p) => void points.push(p) },
    EVENTS_KEY: key ?? undefined,
  };
  return { env, points, assets };
}

function post(
  body: unknown,
  headers: Record<string, string> = { 'Sec-Fetch-Site': 'same-origin' },
  cf: unknown = { country: 'DK', city: 'Aarhus', latitude: '56.1' },
): Request {
  const r = new Request(`${SITE}/e`, {
    method: 'POST',
    body: typeof body === 'string' ? body : JSON.stringify(body),
    headers: { 'CF-Connecting-IP': IP, 'User-Agent': UA, ...headers },
  });
  Object.defineProperty(r, 'cf', { value: cf });
  return r;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('POST /e', () => {
  it('stores an event as one row and one structured log line', async () => {
    const log = vi.spyOn(console, 'log').mockImplementation(() => {});
    const { env, points } = fakeEnv();
    const res = await handle(post(BODY), env, DAY);
    expect(res.status).toBe(204);
    expect(res.headers.get('Cache-Control')).toBe('no-store');
    expect(points).toHaveLength(1);
    const visitor = await visitorKey('secret', DAY, IP, UA);
    expect(visitor).toMatch(/^[0-9a-f]{16}$/);
    const stored = { ...BODY, visitor, country: 'DK' };
    const [p] = points;
    expect(p.indexes).toEqual(['export']);
    expect(p.blobs).toEqual([
      'loose-squares',
      'light',
      'custom',
      '112233-ddeeff-ff8800',
      'saved',
      visitor,
      'DK',
      'loose-squares',
      'default',
      'png',
      '16:9',
      'screen',
      '',
      '',
      '',
    ]);
    expect(p.doubles).toEqual([2560, 1440, 1, 0, 1]);
    expect(log).toHaveBeenCalledTimes(1);
    expect(log.mock.calls[0]).toEqual([stored]);
    const logged = JSON.stringify(log.mock.calls[0]) + JSON.stringify(p);
    for (const secret of [IP, 'Firefox', 'Aarhus', '56.1']) expect(logged).not.toContain(secret);
  });

  it('accepts a matching Origin when Sec-Fetch-Site is absent', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    const { env, points } = fakeEnv();
    const res = await handle(post({ ...BODY, event: 'share' }, { Origin: SITE }), env, DAY);
    expect(res.status).toBe(204);
    expect(points[0].indexes).toEqual(['share']);
  });

  it('stores an empty country when cf has none', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
    const { env, points } = fakeEnv();
    await handle(post(BODY, undefined, null), env, DAY);
    expect(points[0].blobs[BLOBS.indexOf('country')]).toBe('');
  });

  it('answers 405 with Allow to other methods', async () => {
    const { env, points } = fakeEnv();
    for (const method of ['GET', 'PUT', 'HEAD']) {
      const res = await handle(new Request(`${SITE}/e`, { method }), env, DAY);
      expect(res.status).toBe(405);
      expect(res.headers.get('Allow')).toBe('POST');
    }
    expect(points).toHaveLength(0);
  });

  it('answers 403 across sites', async () => {
    const { env, points } = fakeEnv();
    const cases: Record<string, string>[] = [
      { 'Sec-Fetch-Site': 'cross-site' },
      { 'Sec-Fetch-Site': 'same-site', Origin: SITE },
      { Origin: 'https://evil.example' },
      { Origin: 'null' },
      {},
    ];
    for (const headers of cases)
      expect((await handle(post(BODY, headers), env, DAY)).status).toBe(403);
    expect(points).toHaveLength(0);
  });

  it('answers 413 to a large body', async () => {
    const { env, points } = fakeEnv();
    const big = JSON.stringify({ ...BODY, pad: 'x'.repeat(MAX_BODY) });
    expect((await handle(post(big), env, DAY)).status).toBe(413);
    // A declared length over the cap is refused before the body is read.
    const declared = post(BODY, {
      'Sec-Fetch-Site': 'same-origin',
      'Content-Length': String(MAX_BODY + 1),
    });
    expect((await handle(declared, env, DAY)).status).toBe(413);
    expect(points).toHaveLength(0);
  });

  it('answers 400 to malformed events', async () => {
    const { env, points } = fakeEnv();
    for (const body of ['', 'nope', '{}', { ...BODY, event: 'view' }, { ...BODY, w: 'wide' }])
      expect((await handle(post(body), env, DAY)).status).toBe(400);
    expect(points).toHaveLength(0);
  });

  it('answers 503 and stores nothing without EVENTS_KEY', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    const { env, points } = fakeEnv(null);
    expect((await handle(post(BODY), env, DAY)).status).toBe(503);
    expect(points).toHaveLength(0);
    expect(error).toHaveBeenCalledTimes(1);
  });

  it('answers 500 instead of throwing when the write fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { env } = fakeEnv();
    env.EVENTS.writeDataPoint = () => {
      throw new Error('down');
    };
    expect((await handle(post(BODY), env, DAY)).status).toBe(500);
  });
});

describe('visitorKey', () => {
  it('holds within a UTC day and changes across days', async () => {
    const a = await visitorKey('k', new Date('2026-10-04T00:00:00Z'), IP, UA);
    expect(await visitorKey('k', new Date('2026-10-04T23:59:59Z'), IP, UA)).toBe(a);
    expect(await visitorKey('k', new Date('2026-10-05T00:00:00Z'), IP, UA)).not.toBe(a);
  });

  it('differs by address, browser and secret', async () => {
    const a = await visitorKey('k', DAY, IP, UA);
    expect(await visitorKey('k', DAY, '203.0.113.8', UA)).not.toBe(a);
    expect(await visitorKey('k', DAY, IP, `${UA} `)).not.toBe(a);
    expect(await visitorKey('other', DAY, IP, UA)).not.toBe(a);
    expect(a).not.toContain(IP);
  });
});

describe('other paths', () => {
  it('serves the static assets', async () => {
    const { env, assets, points } = fakeEnv();
    const req = new Request(`${SITE}/about`);
    const res = await handle(req, env, DAY);
    expect(await res.text()).toBe('asset');
    expect(assets).toEqual([req]);
    expect(points).toHaveLength(0);
  });
});
