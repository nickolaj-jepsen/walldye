/**
 * The detail page's Drawing controls as data: the knobs a piece shows, the visitor's edits to a
 * version's params, and how edits read in the query string, file names and the run command. No DOM,
 * so vitest covers it.
 */

export type ParamValue = number | string | boolean | null;

/** A knob as the page shows it (src/content.config.ts `knobs`). */
export interface Knob {
  name: string;
  label: string;
  kind: 'int' | 'float' | 'bool' | 'str';
  lo: number | null;
  hi: number | null;
  choices: { value: number | string; label: string }[] | null;
  unit: string;
  /** The longest text a text knob takes; null for any other knob. */
  maxLen: number | null;
  /** The axis along which dragging the picture moves this knob, if any. */
  drag: 'x' | 'y' | null;
}

/** Whether `k` takes free text. */
export const isText = (k: Knob): boolean => k.kind === 'str' && !k.choices && k.maxLen !== null;

/** Whether `text` is a value of text knob `k`: 1 to maxLen printable ASCII characters. */
export function validText(k: Knob, text: string): boolean {
  return text.length >= 1 && text.length <= (k.maxLen ?? 0) && /^[\x20-\x7e]*$/.test(text);
}

/** The visitor's changes to the version on show: a draw number (the seed) and knob values that differ from the version's. */
export interface Edits {
  draw: number | null;
  knobs: Record<string, ParamValue>;
}

/** Draw numbers "Draw another" picks from, both included. */
export const DRAW_MIN = 1;
export const DRAW_MAX = 9999;
/** Draws "Draw another" tries before it gives up. */
export const DRAW_TRIES = 5;

export const noEdits = (): Edits => ({ draw: null, knobs: {} });

export function isEdited(e: Edits): boolean {
  return e.draw !== null || Object.keys(e.knobs).length > 0;
}

/** The params a draw overrides on the version's: the edited knobs, and `seed` for a draw number. */
export function overrides(e: Edits): Record<string, ParamValue> {
  return e.draw === null ? { ...e.knobs } : { ...e.knobs, seed: e.draw };
}

/** A draw number other than `current`, uniform over DRAW_MIN..DRAW_MAX; `random` returns [0, 1). */
export function pickDraw(current: number | null, random: () => number = Math.random): number {
  const span = DRAW_MAX - DRAW_MIN + 1;
  for (;;) {
    const n = DRAW_MIN + Math.floor(random() * span);
    if (n !== current) return n;
  }
}

/** `n` with at most `places` decimals and no trailing zeros. */
function num(n: number, places = 4): string {
  const s = n.toFixed(places);
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s;
}

/** A range knob's slider step: 1 for an int, else about a hundredth of the range, rounded down to 1, 2 or 5 times a power of ten. */
export function knobStep(k: Knob): number {
  if (k.kind === 'int') return 1;
  const raw = ((k.hi ?? 1) - (k.lo ?? 0)) / 100;
  if (!(raw > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [5, 2, 1].map((m) => m * p).find((s) => s <= raw) ?? p;
}

/** `v` snapped to the knob's slider step from `lo`, as the slider itself would. */
function snap(k: Knob, v: number): number {
  const step = knobStep(k);
  const lo = k.lo ?? 0;
  return Number(num(lo + Math.round((v - lo) / step) * step, 6));
}

/** The number shown beside a range knob: whole numbers for an int, degrees with ° for an angle, else none. */
export function readout(k: Knob, v: ParamValue): string | null {
  if (typeof v !== 'number' || k.choices) return null;
  if (k.kind === 'int') return String(v);
  if (k.unit === 'deg') return `${num(v, 1)}°`;
  return null;
}

/** `v` clamped to the knob's lo..hi and snapped to its slider's step; ints come out whole. */
export function fitRange(k: Knob, v: number): number {
  const out = snap(k, Math.min(k.hi ?? Infinity, Math.max(k.lo ?? -Infinity, v)));
  return k.kind === 'int' ? Math.round(out) : out;
}

/**
 * `text` from the query string as a value of `k`: a choice by its value, a bool as true or false,
 * text as given when valid, a number fitted to the range. undefined for anything else.
 */
export function parseKnob(k: Knob, text: string): ParamValue | undefined {
  if (k.choices) return k.choices.find((c) => String(c.value) === text)?.value;
  if (k.kind === 'bool') return text === 'true' ? true : text === 'false' ? false : undefined;
  if (isText(k)) return validText(k, text) ? text : undefined;
  if (k.kind === 'str' || !/^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) return undefined;
  return fitRange(k, Number(text));
}

/** The value of drag knob `k` after the pointer moved `share` of the picture from where `from` was set: the whole picture spans lo..hi. */
export function dragValue(k: Knob, from: number, share: number): number {
  return fitRange(k, from + share * ((k.hi ?? 0) - (k.lo ?? 0)));
}

/** A draw number from the query string: DRAW_MIN or more, at most nine digits; undefined otherwise. */
export function parseDraw(text: string | null): number | undefined {
  if (text === null || !/^\d{1,9}$/.test(text)) return undefined;
  const n = Number(text);
  return n >= DRAW_MIN ? n : undefined;
}

function show(v: ParamValue): string {
  return typeof v === 'number' ? num(v) : String(v);
}

/**
 * The edits read from `query` against the version's `params`: `draw` and every shown knob whose
 * parsed value differs from the version's. Values that do not parse are ignored.
 */
export function editsFromQuery(query: URLSearchParams, knobs: readonly Knob[], params: Record<string, ParamValue>, redraw: boolean): Edits {
  const e = noEdits();
  const d = redraw ? parseDraw(query.get('draw')) : undefined;
  if (d !== undefined && d !== params.seed) e.draw = d;
  for (const k of knobs) {
    const text = query.get(k.name);
    const v = text === null ? undefined : parseKnob(k, text);
    if (v !== undefined && v !== params[k.name]) e.knobs[k.name] = v;
  }
  return e;
}

/** The query entries for `e`: the edited knobs in the order of `knobs`, then `draw`. */
export function editsQuery(e: Edits, knobs: readonly Knob[]): [string, string][] {
  const out: [string, string][] = knobs.filter((k) => Object.hasOwn(e.knobs, k.name)).map((k) => [k.name, show(e.knobs[k.name])]);
  if (e.draw !== null) out.push(['draw', String(e.draw)]);
  return out;
}

/** The run command's `--set` items for `e`: each edited knob, then `seed=<draw>`. */
export function setItems(e: Edits, knobs: readonly Knob[]): string[] {
  return editsQuery(e, knobs).map(([k, v]) => `${k === 'draw' ? 'seed' : k}=${v}`);
}

/**
 * The part of a file name that names `e`: `-<knob><value>` per edited knob, then `-draw<n>`; ''
 * when unedited. Runs of other characters become `_`, and a value keeps at most SUFFIX_CHARS.
 */
export function editsSuffix(e: Edits, knobs: readonly Knob[]): string {
  return editsQuery(e, knobs)
    .map(([k, v]) => `-${k}${v.replace(/[^A-Za-z0-9.]+/g, '_').slice(0, SUFFIX_CHARS)}`)
    .join('');
}

const SUFFIX_CHARS = 16;

/** `s` as one POSIX shell word: unchanged when it is plain, else single-quoted. */
export function shellWord(s: string): string {
  return /^[\w.,:=+@%/-]+$/.test(s) ? s : `'${s.replace(/'/g, `'\\''`)}'`;
}
