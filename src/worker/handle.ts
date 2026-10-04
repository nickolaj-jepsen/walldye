/**
 * The site Worker's request handler. On `/e` it answers 405 to anything but POST; a POST has its
 * event checked, gets the visitor key and the country, and is written as one Analytics Engine row
 * and logged with the same fields. Typed structurally, so it also type-checks against the DOM lib.
 */
import {
  type ClientEvent,
  EVENT_PATH,
  encodeEvent,
  MAX_BODY,
  parseEvent,
  type StoredEvent,
} from '../lib/events';

export interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  EVENTS: {
    writeDataPoint(point: { indexes: string[]; blobs: string[]; doubles: number[] }): void;
  };
  /** HMAC key for the daily visitor key; a secret, from `.dev.vars` locally. */
  EVENTS_KEY?: string;
}

const encoder = new TextEncoder();

function reply(status: number, headers: Record<string, string> = {}): Response {
  return new Response(null, { status, headers: { 'Cache-Control': 'no-store', ...headers } });
}

/** Sec-Fetch-Site when the browser sends it, else the Origin header's host against the request's. */
function sameOrigin(request: Request, url: URL): boolean {
  const site = request.headers.get('Sec-Fetch-Site');
  if (site !== null) return site === 'same-origin';
  const origin = request.headers.get('Origin');
  if (!origin) return false;
  try {
    return new URL(origin).host === url.host;
  } catch {
    return false;
  }
}

/** The body as text, or null once it passes `max` bytes. */
async function readCapped(request: Request, max: number): Promise<string | null> {
  const declared = Number(request.headers.get('Content-Length'));
  if (declared > max) return null;
  if (!request.body) return '';
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) {
    all.set(c, at);
    at += c.byteLength;
  }
  return new TextDecoder().decode(all);
}

async function hmac(key: BufferSource, data: string): Promise<ArrayBuffer> {
  const k = await crypto.subtle.importKey('raw', key, { name: 'HMAC', hash: 'SHA-256' }, false, [
    'sign',
  ]);
  return crypto.subtle.sign('HMAC', k, encoder.encode(data));
}

/**
 * The visitor key: 16 hex digits of HMAC(HMAC(secret, UTC date), ip + "\n" + userAgent). It changes
 * every UTC day and cannot be turned back into the address without the secret.
 */
export async function visitorKey(
  secret: string,
  now: Date,
  ip: string,
  userAgent: string,
): Promise<string> {
  const day = await hmac(encoder.encode(secret), now.toISOString().slice(0, 10));
  const id = new Uint8Array(await hmac(day, `${ip}\n${userAgent}`));
  return [...id.subarray(0, 8)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** `cf.country` when it is a two-character code, else "". */
function countryOf(request: Request): string {
  const country = (request as { cf?: { country?: unknown } }).cf?.country;
  return typeof country === 'string' && /^[A-Z0-9]{2}$/.test(country) ? country : '';
}

async function accept(request: Request, env: Env, url: URL, now: Date): Promise<Response> {
  if (request.method !== 'POST') return reply(405, { Allow: 'POST' });
  if (!sameOrigin(request, url)) return reply(403);
  const text = await readCapped(request, MAX_BODY);
  if (text === null) return reply(413);
  const event: ClientEvent | null = parseEvent(text);
  if (!event) return reply(400);
  if (!env.EVENTS_KEY) {
    console.error('EVENTS_KEY is not set; event dropped');
    return reply(503);
  }
  const visitor = await visitorKey(
    env.EVENTS_KEY,
    now,
    request.headers.get('CF-Connecting-IP') ?? '',
    request.headers.get('User-Agent') ?? '',
  );
  const stored: StoredEvent = { ...event, visitor, country: countryOf(request) };
  env.EVENTS.writeDataPoint(encodeEvent(stored));
  // An object, so Workers Logs indexes every field.
  console.log(stored);
  return reply(204);
}

/**
 * `/e` gets the event response and any other path the assets; never throws (500 on an unexpected
 * error). `now` picks the visitor key's day.
 */
export async function handle(request: Request, env: Env, now = new Date()): Promise<Response> {
  const url = new URL(request.url);
  if (url.pathname !== EVENT_PATH) return env.ASSETS.fetch(request);
  try {
    return await accept(request, env, url, now);
  } catch (e) {
    console.error('event failed', e instanceof Error ? e.message : String(e));
    return reply(500);
  }
}
