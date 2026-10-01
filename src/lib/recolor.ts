/**
 * The browser recolor, a port of walldye/tools/recolor.py select() and recolor(): a template's color
 * slots are set from the seeds through the per-occurrence coefficients in slots.json.
 */

import { hexToRgb, isFireproof, type Regime, regimeOf, rgbToHex, type Seeds } from './theme';
import { findColors, joinSlots, splitSlots } from './tokenize';

/** One slots.json template entry, keyed "<aspect>/<regime>". coefs rows are [a, b, c, dr, dg, db]; occ[i] is slot i's row. */
export interface SlotsEntry {
  file: string;
  sha256: string;
  n: number;
  coefs: number[][];
  occ: number[];
}

/** A parsed build/slots.json: the piece fields plus one SlotsEntry per "<aspect>/<regime>" key. */
export interface Slots {
  design_sha: string;
  toolchain: string;
  focus: [number, number];
  cells: number[];
  [key: string]: unknown;
}

/** A template split at its color slots, so recoloring it repeatedly skips the tokenizer. */
export interface PreparedTemplate {
  svg: string;
  parts: string[];
}

/** The entry to recolor with and its slots.json key. */
export interface Picked {
  key: string;
  entry: SlotsEntry;
}

/** The part of a file's sha256 its served URL carries. */
export const servedHash = (sha256: string): string => sha256.slice(0, 12);

/** Where the site serves a template or slots.json by its content: /t/<servedHash>.svg or .slots.json. */
export function servedUrl(hash: string, kind: 'svg' | 'slots.json'): string {
  return `/t/${hash}.${kind}`;
}

/** Where the site serves the template `entry` describes. */
export function templateUrl(entry: SlotsEntry): string {
  return servedUrl(servedHash(entry.sha256), 'svg');
}

export function isEntry(value: unknown): value is SlotsEntry {
  return typeof value === 'object' && value !== null && 'file' in value;
}

/** The SlotsEntry values of `slots` by key, in file order. */
export function entries(slots: Slots): [string, SlotsEntry][] {
  return Object.entries(slots).filter((e): e is [string, SlotsEntry] => isEntry(e[1]));
}

/** The entry "<aspect>/<regime>" for `aspect` (like "16:9"); throws when the piece has none. */
export function pickTemplate(slots: Slots, aspect: string, regime: Regime): Picked {
  const key = `${aspect}/${regime}`;
  const entry = Object.hasOwn(slots, key) ? slots[key] : undefined;
  if (!isEntry(entry)) throw new Error(`no ${key} entry in slots.json`);
  return { key, entry };
}

/** Python recolor.select(): the picked entry for `seeds`, in their regime. */
export function select(slots: Slots, aspect: string, seeds: Seeds): Picked {
  return pickTemplate(slots, aspect, regimeOf(seeds));
}

export function prepareTemplate(svg: string): PreparedTemplate {
  return { svg, parts: splitSlots(svg, findColors(svg)) };
}

/**
 * `template` (the file `entry` names) recolored for `seeds`. Slot i becomes coefs[occ[i]] =
 * [a, b, c, dr, dg, db] evaluated per channel as ((a*bg + b*fg) + c*accent) + d, rounded half to even
 * and clamped.
 *
 * Returns the template unchanged for exact fireproof seeds, and as the fallback when its slot count is
 * not `entry.n` or `entry.occ` does not index `entry.coefs` once per slot.
 */
export function recolor(
  template: string | PreparedTemplate,
  entry: SlotsEntry,
  seeds: Seeds,
): string {
  const prepared = typeof template === 'string' ? prepareTemplate(template) : template;
  const n = prepared.parts.length - 1;
  if (
    isFireproof(seeds) ||
    n !== entry.n ||
    entry.occ.length !== n ||
    entry.occ.some((o) => !Array.isArray(entry.coefs[o]))
  ) {
    return prepared.svg;
  }
  const bg = hexToRgb(seeds.bg);
  const fg = hexToRgb(seeds.fg);
  const accent = hexToRgb(seeds.accent);
  const rows = entry.coefs.map(([a, b, c, ...d]) => {
    const ch = (i: number) => a * bg[i] + b * fg[i] + c * accent[i] + d[i];
    return rgbToHex(ch(0), ch(1), ch(2));
  });
  return joinSlots(
    prepared.parts,
    entry.occ.map((o) => rows[o]),
  );
}
