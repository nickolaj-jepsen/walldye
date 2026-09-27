/**
 * The browser recolour, a port of walldye/tools/build.py select() and recolour(): a template's colour
 * slots are set from the seeds through the per-occurrence coefficients in slots.json.
 */

import { hexToRgb, isLight, normaliseSeeds, PRESETS, rgbToHex, type Regime, type Seeds } from './theme';
import { findColours, joinSlots, splitSlots } from './tokenize';

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
  focus: [number, number];
  cells: number[];
  probes: Record<string, string>;
  checked: string;
  [key: string]: unknown;
}

/** A template split at its colour slots, so recolouring it repeatedly skips the tokenizer. */
export interface PreparedTemplate {
  svg: string;
  parts: string[];
}

/** The entry to recolour with; `swap` means apply the seeds with bg and fg exchanged. */
export interface Picked {
  key: string;
  entry: SlotsEntry;
  swap: boolean;
}

/** Whether `value` looks like a slots.json template entry. */
export function isEntry(value: unknown): value is SlotsEntry {
  return typeof value === 'object' && value !== null && 'file' in value;
}

/** The SlotsEntry values of `slots` by key, in file order. */
export function entries(slots: Slots): [string, SlotsEntry][] {
  return Object.entries(slots).filter((e): e is [string, SlotsEntry] => isEntry(e[1]));
}

/**
 * The entry for `aspect` (like "16:9") in `regime`: "<aspect>/<regime>", except that a piece without a
 * light entry (a `themes: [dark]` piece) uses its dark entry with `swap` under light seeds.
 * Throws when the piece has no dark entry for `aspect`.
 */
export function pickTemplate(slots: Slots, aspect: string, regime: Regime): Picked {
  const light = `${aspect}/light`;
  if (regime === 'light' && Object.hasOwn(slots, light) && isEntry(slots[light])) {
    return { key: light, entry: slots[light], swap: false };
  }
  const key = `${aspect}/dark`;
  const entry = slots[key];
  if (!isEntry(entry)) throw new Error(`no ${key} entry in slots.json`);
  return { key, entry, swap: regime === 'light' };
}

/** `seeds` normalised, with bg and fg exchanged when `swap`: the theme a picked entry is evaluated under. */
export function appliedSeeds(seeds: Seeds, swap = false): Seeds {
  const s = normaliseSeeds(seeds);
  return swap ? { bg: s.fg, fg: s.bg, accent: s.accent } : s;
}

/** Python build.select(): the picked entry for `seeds` plus the seeds to apply (swapped when the entry needs it). */
export function select(slots: Slots, aspect: string, seeds: Seeds): Picked & { seeds: Seeds } {
  const s = normaliseSeeds(seeds);
  const picked = pickTemplate(slots, aspect, isLight(s.bg, s.fg) ? 'light' : 'dark');
  return { ...picked, seeds: appliedSeeds(s, picked.swap) };
}

/** `svg` split at its colour slots, for repeated recolour() calls. */
export function prepareTemplate(svg: string): PreparedTemplate {
  return { svg, parts: splitSlots(svg, findColours(svg)) };
}

const FIREPROOF = PRESETS.fireproof;

/**
 * `template` (the file `entry` names) recoloured for `seeds`, with bg and fg exchanged first when
 * `opts.swap` (see pickTemplate). Slot i becomes coefs[occ[i]] = [a, b, c, dr, dg, db] evaluated per
 * channel as ((a*bg + b*fg) + c*accent) + d, rounded half to even and clamped.
 *
 * Returns the template unchanged for exact fireproof seeds (after any swap), and as the fallback when
 * its slot count is not `entry.n` or `entry.occ` does not index `entry.coefs` once per slot.
 * Throws on an invalid seed.
 */
export function recolour(template: string | PreparedTemplate, entry: SlotsEntry, seeds: Seeds, opts: { swap?: boolean } = {}): string {
  const prepared = typeof template === 'string' ? prepareTemplate(template) : template;
  const s = appliedSeeds(seeds, opts.swap);
  const n = prepared.parts.length - 1;
  const fireproof = s.bg === FIREPROOF.bg && s.fg === FIREPROOF.fg && s.accent === FIREPROOF.accent;
  if (fireproof || n !== entry.n || entry.occ.length !== n || entry.occ.some((o) => !Array.isArray(entry.coefs[o]))) {
    return prepared.svg;
  }
  const bg = hexToRgb(s.bg);
  const fg = hexToRgb(s.fg);
  const accent = hexToRgb(s.accent);
  const rows = entry.coefs.map(([a, b, c, ...d]) => {
    const ch = (i: number) => a * bg[i] + b * fg[i] + c * accent[i] + d[i];
    return rgbToHex(ch(0), ch(1), ch(2));
  });
  return joinSlots(
    prepared.parts,
    entry.occ.map((o) => rows[o]),
  );
}
