/**
 * The product events the client posts to the Worker and the Analytics Engine row it writes.
 * Validation rejects only malformed input; values such as `format` or `kind` are stored as sent.
 * The client imports only types from here, so its bundle carries no zod.
 */
import * as z from 'zod/mini';

/** Largest request body the Worker reads, in bytes. */
export const MAX_BODY = 2048;
/** Longest string field, in UTF-16 code units. */
export const MAX_TEXT = 64;
/** Largest screen side in device pixels. */
export const MAX_PIXELS = 65536;
/** Largest device pixel ratio. */
export const MAX_DPR = 16;

export const EXPORT_FORMATS = ['svg', 'png', 'webp', 'jpeg'] as const;
export const THEME_KINDS = ['preset', 'family', 'custom', 'keep', 'drop'] as const;
/** Where a theme change came from; `keep` and `drop` come from the `shared` line. */
export const THEME_VIAS = ['picker', 'index', 'hex', 'wheel', 'import', 'shared'] as const;
export type ThemeKind = (typeof THEME_KINDS)[number];
export type ThemeVia = (typeof THEME_VIAS)[number];

const text = z.string().check(z.maxLength(MAX_TEXT));
const flag = z.boolean();
const pixels = z.int().check(z.minimum(0), z.maximum(MAX_PIXELS));
const ratio = z.number().check(z.positive(), z.maximum(MAX_DPR));

/**
 * Each event's own fields. An export counts once the file is handed to the browser: `version` is
 * the variant or `default`, `size` is `<w>x<h>`, `screen` or `svg`, and `first` marks the slug's
 * first export since the page loaded. A theme change's `name` is the preset, the family or `custom`.
 */
export const EVENT_FIELDS = {
  export: { slug: text, version: text, format: text, aspect: text, size: text, first: flag },
  theme: { kind: text, name: text, via: text },
  share: {},
};

/** Sent with every event; `theme`, `token` and `source` describe the theme after the event. */
export const CONTEXT_FIELDS = {
  page: text,
  w: pixels,
  h: pixels,
  dpr: ratio,
  phone: flag,
  scheme: text,
  theme: text,
  token: text,
  source: text,
};

/** Added by the Worker: the daily visitor key and the two-letter country, or "". */
export const WORKER_FIELDS = { visitor: text, country: text };

/** Every field's schema by name, for checking stored values one field at a time. */
export const FIELDS = {
  ...CONTEXT_FIELDS,
  ...WORKER_FIELDS,
  ...EVENT_FIELDS.export,
  ...EVENT_FIELDS.theme,
};

const EventBody = z.discriminatedUnion('event', [
  z.object({ event: z.literal('export'), ...EVENT_FIELDS.export }),
  z.object({ event: z.literal('theme'), ...EVENT_FIELDS.theme }),
  z.object({ event: z.literal('share') }),
]);
const Context = z.object(CONTEXT_FIELDS);

export type EventName = keyof typeof EVENT_FIELDS;
/** An event as the page code fires it, before the context is added. */
export type EventBody = z.infer<typeof EventBody>;
export type Context = z.infer<typeof Context>;
export type ClientEvent = EventBody & Context;
export type StoredEvent = ClientEvent & z.infer<z.ZodMiniObject<typeof WORKER_FIELDS>>;

/** Analytics Engine columns after index1 (the event name), read by position: new fields go last. */
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

/** The Analytics Engine column holding `field` (`blob<n>` or `double<n>`); throws for a field no column holds. */
export function column(field: string): string {
  const blob = (BLOBS as readonly string[]).indexOf(field);
  if (blob >= 0) return `blob${blob + 1}`;
  const double = (DOUBLES as readonly string[]).indexOf(field);
  if (double >= 0) return `double${double + 1}`;
  throw new Error(`no column holds ${field}`);
}

export interface DataPoint {
  indexes: [string];
  blobs: string[];
  doubles: number[];
}

/** The event in `body` with only its own and the context fields, or null when it is malformed. */
export function validateEvent(body: unknown): ClientEvent | null {
  const event = EventBody.safeParse(body);
  const context = Context.safeParse(body);
  return event.success && context.success ? { ...event.data, ...context.data } : null;
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
  const fields = e as Partial<Record<keyof typeof FIELDS, string | number | boolean>>;
  return {
    indexes: [e.event],
    blobs: BLOBS.map((k) => String(fields[k] ?? '')),
    doubles: DOUBLES.map((k) => Number(fields[k] ?? 0)),
  };
}

/** The inverse of encodeEvent(), or null when `index` is no event name. */
export function decodeEvent(
  index: string,
  blobs: readonly string[],
  doubles: readonly number[],
): StoredEvent | null {
  if (!Object.hasOwn(EVENT_FIELDS, index)) return null;
  const own = { ...EVENT_FIELDS[index as EventName], ...CONTEXT_FIELDS, ...WORKER_FIELDS };
  const out: Record<string, unknown> = { event: index };
  BLOBS.forEach((k, i) => {
    if (Object.hasOwn(own, k)) out[k] = blobs[i] ?? '';
  });
  DOUBLES.forEach((k, i) => {
    if (Object.hasOwn(own, k))
      out[k] = FIELDS[k].type === 'boolean' ? doubles[i] === 1 : (doubles[i] ?? 0);
  });
  return out as StoredEvent;
}
