/**
 * The site's product events: what the client sends to `POST /e`, what the Worker checks and adds,
 * and the Analytics Engine row it writes. Pure, so the client and the Worker share it.
 *
 * The Worker rejects only malformed input: an unknown event name, or a field missing, of the wrong
 * type or out of bounds. It stores values as sent, so readers of the rows check them against the
 * lists below.
 */

export const EVENT_PATH = '/e';
/** Largest request body the Worker reads, in bytes. */
export const MAX_BODY = 2048;
/** Longest string field, in UTF-16 code units. */
export const MAX_TEXT = 64;
/** Largest screen side in device pixels. */
export const MAX_PIXELS = 65536;
/** Largest device pixel ratio. */
export const MAX_DPR = 16;

/** `text`: a string of at most MAX_TEXT; `flag`: a boolean; `pixels`: an integer 0..MAX_PIXELS; `ratio`: a number over 0 up to MAX_DPR. */
type FieldType = 'text' | 'flag' | 'pixels' | 'ratio';
type Value<T extends FieldType> = T extends 'text' ? string : T extends 'flag' ? boolean : number;
type Shape<S extends Record<string, FieldType>> = { -readonly [K in keyof S]: Value<S[K]> };

/**
 * Every event's own fields.
 * - export, after the file was handed to the browser: `version` is the variant name, `default` for
 *   the default version; `size` is `<w>x<h>`, `screen` for the screen-size choice, or `svg`; `first`
 *   is true for the first finished export of that slug since the page loaded.
 * - theme, after the visitor changed the theme: see THEME_KINDS and THEME_VIAS; `name` is the
 *   preset or family name, `custom` for a custom theme.
 * - share, after "Copy link" copied.
 */
export const EVENT_FIELDS = {
  export: {
    slug: 'text',
    version: 'text',
    format: 'text',
    aspect: 'text',
    size: 'text',
    first: 'flag',
  },
  theme: { kind: 'text', name: 'text', via: 'text' },
  share: {},
} as const satisfies Record<string, Record<string, FieldType>>;

/**
 * Sent with every event: `page` is `index`, `about`, `404` or the slug; `w` and `h` the screen in
 * device pixels; `scheme` the system's `light` or `dark`; `theme`, `token` and `source` the theme
 * in effect after the event (preset name or `custom`, canonical token, `shared`, `saved` or `system`).
 */
export const CONTEXT_FIELDS = {
  page: 'text',
  w: 'pixels',
  h: 'pixels',
  dpr: 'ratio',
  phone: 'flag',
  scheme: 'text',
  theme: 'text',
  token: 'text',
  source: 'text',
} as const satisfies Record<string, FieldType>;

/** Added by the Worker: the daily visitor key (16 hex digits) and the two-letter country, or "". */
export const WORKER_FIELDS = { visitor: 'text', country: 'text' } as const;

export const EXPORT_FORMATS = ['svg', 'png', 'webp', 'jpeg'] as const;
export const THEME_KINDS = ['preset', 'family', 'custom', 'keep', 'drop'] as const;
/** Where a theme change came from; `keep` and `drop` come from the `shared` line. */
export const THEME_VIAS = ['picker', 'index', 'hex', 'wheel', 'import', 'shared'] as const;
export type ThemeKind = (typeof THEME_KINDS)[number];
export type ThemeVia = (typeof THEME_VIAS)[number];

export type EventName = keyof typeof EVENT_FIELDS;
export type Context = Shape<typeof CONTEXT_FIELDS>;
/** An event as the page code fires it, before the context is added. */
export type EventBody = {
  [K in EventName]: { event: K } & Shape<(typeof EVENT_FIELDS)[K]>;
}[EventName];
/** An event as the client sends it. */
export type ClientEvent = EventBody & Context;
/** An event as the Worker stores it. */
export type StoredEvent = ClientEvent & Shape<typeof WORKER_FIELDS>;

/** Analytics Engine row layout: index1 is the event name, then these blobs and doubles in order. */
export const BLOBS = [
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
] as const;
/** Booleans are stored as 0 or 1. */
export const DOUBLES = ['w', 'h', 'dpr', 'phone', 'first'] as const;

export interface DataPoint {
  indexes: [string];
  blobs: string[];
  doubles: number[];
}

/** Every field's type: context, Worker and event fields alike. */
const SCHEMA: Record<string, FieldType> = {
  ...CONTEXT_FIELDS,
  ...WORKER_FIELDS,
  ...Object.assign({}, ...Object.values(EVENT_FIELDS)),
};

function isEventName(v: unknown): v is EventName {
  return typeof v === 'string' && Object.hasOwn(EVENT_FIELDS, v);
}

function valid(type: FieldType, v: unknown): boolean {
  switch (type) {
    case 'text':
      return typeof v === 'string' && v.length <= MAX_TEXT;
    case 'flag':
      return typeof v === 'boolean';
    case 'pixels':
      return Number.isInteger(v) && (v as number) >= 0 && (v as number) <= MAX_PIXELS;
    case 'ratio':
      return Number.isFinite(v) && (v as number) > 0 && (v as number) <= MAX_DPR;
  }
}

/**
 * The event in `body`, keeping only its own and the context fields, or null when the event name is
 * unknown or any of those fields is missing, of the wrong type or out of bounds.
 */
export function validateEvent(body: unknown): ClientEvent | null {
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return null;
  const input = body as Record<string, unknown>;
  const name = input.event;
  if (!isEventName(name)) return null;
  const out: Record<string, unknown> = { event: name };
  const fields: Record<string, FieldType> = { ...EVENT_FIELDS[name], ...CONTEXT_FIELDS };
  for (const [key, type] of Object.entries(fields)) {
    if (!Object.hasOwn(input, key) || !valid(type, input[key])) return null;
    out[key] = input[key];
  }
  return out as ClientEvent;
}

/** validateEvent() over JSON text; null when it does not parse. */
export function parseEvent(text: string): ClientEvent | null {
  try {
    return validateEvent(JSON.parse(text));
  } catch {
    return null;
  }
}

/** The Analytics Engine row for `e`; fields the event lacks are "" or 0. */
export function encodeEvent(e: StoredEvent): DataPoint {
  const fields = e as unknown as Record<string, string | number | boolean | undefined>;
  return {
    indexes: [e.event],
    blobs: BLOBS.map((k) => String(fields[k] ?? '')),
    doubles: DOUBLES.map((k) => Number(fields[k] ?? 0)),
  };
}

/** The event a row holds, or null when its index is no event name; the inverse of encodeEvent(). */
export function decodeEvent(
  index: string,
  blobs: readonly string[],
  doubles: readonly number[],
): StoredEvent | null {
  if (!isEventName(index)) return null;
  const keep = new Set([
    ...Object.keys(EVENT_FIELDS[index]),
    ...Object.keys(CONTEXT_FIELDS),
    ...Object.keys(WORKER_FIELDS),
  ]);
  const out: Record<string, unknown> = { event: index };
  BLOBS.forEach((k, i) => {
    if (keep.has(k)) out[k] = blobs[i] ?? '';
  });
  DOUBLES.forEach((k, i) => {
    if (keep.has(k)) out[k] = SCHEMA[k] === 'flag' ? doubles[i] === 1 : (doubles[i] ?? 0);
  });
  return out as StoredEvent;
}
