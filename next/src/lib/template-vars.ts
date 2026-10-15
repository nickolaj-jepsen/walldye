/**
 * The CSS-variable form of a template: every color slot reads the seed channels the theme boot sets
 * on `:root` (`--bg-r` .. `--ac-b`, 0..255) and the regime switches `--dk`/`--lt` (1/0), so a theme
 * change restyles a plate without a fetch.
 *
 * A build file that both regimes share (the usual case) becomes one var template serving both: each
 * slot reads `--c<k>`, where k numbers the distinct (dark row, light row) pairs, and `--c<k>` is
 * `--dk * dark color + --lt * light color`. A file only one regime uses gets that regime's rows only.
 * Constant rows (a = b = c = 0, mask content only) stay literal.
 *
 * Every id is namespaced `t<hash>-`, so templates can share a document: `t<hash>-base` is everything
 * but the motif, and `t<hash>-motif` the motif group's children in motif-local units, inside a
 * group that still carries the drawn transform so the file renders on its own. Defs sit inside the
 * base group, and a motif that references one gets its own `-m` copy.
 *
 * On its own, the file renders in the dark regime and the colors the dark regime was drawn in
 * (fireproof), or the light one's (flexoki-light) for a light-only file: every variable falls back.
 */

import { partId } from './catalog';
import { motifTransform, type Placement } from './motif';
import type { SlotsEntry } from './recolor';
import { REGIME_VARS, SEED_VARS } from './seed-vars';
import { hexToRgb, PRESETS, type Regime, regimeOf, rgbToHex, type Seeds } from './theme';
import { findColors } from './tokenize';

export { partId } from './catalog';
export { REGIME_VARS, SEED_VARS, seedVars } from './seed-vars';

/** Bumped whenever the rewrite changes, so codegen redoes every template and renames it. */
export const TEMPLATE_FORMAT = 2;

/** The theme each regime's templates are drawn in, which the variable fallbacks reproduce. */
export const DRAWN_IN: Readonly<Record<Regime, Seeds>> = {
  dark: PRESETS.fireproof,
  light: PRESETS['flexoki-light'],
};

/** A coefficient row: [a, b, c, dr, dg, db], the color a*bg + b*fg + c*accent + d per channel. */
export type Row = readonly number[];

/** The slots.json fields the rewrite reads. */
export type EntryRows = Pick<SlotsEntry, 'coefs' | 'occ' | 'n'>;

/** For each `--c<k>`: the row index it takes in the dark and the light regime, null where the file does not serve that regime. */
export type VarRows = [dark: number | null, light: number | null][];

const fmt = (n: number) => String(Math.round(n * 1e6) / 1e6);

/** True when the row ignores the seeds: a mask's constant gray. */
export function isConstant(row: Row): boolean {
  return row[0] === 0 && row[1] === 0 && row[2] === 0;
}

/** One channel of `row` as a sum over the seed variables, falling back to `regime`'s drawing seeds. */
function channel(row: Row, ch: number, regime: Regime): string {
  const d = DRAWN_IN[regime];
  const drawn = [d.bg, d.fg, d.accent].map(hexToRgb);
  const terms: string[] = [];
  for (let s = 0; s < 3; s++) {
    const k = row[s];
    if (k === 0) continue;
    const v = `var(${SEED_VARS[s][ch]},${drawn[s][ch]})`;
    terms.push(k === 1 ? v : `${fmt(k)}*${v}`);
  }
  const c = row[3 + ch];
  if (c !== 0 || !terms.length) terms.push(fmt(c));
  return terms.join(' + ');
}

/** `--c<k>`'s value: an rgb() over the seed variables, switched by regime when the rows differ. */
function varColor(dark: Row | null, light: Row | null): string {
  const one = (row: Row, regime: Regime, ch: number) => `calc(${channel(row, ch, regime)})`;
  const both = (ch: number) => {
    if (!dark) return one(light as Row, 'light', ch);
    if (!light || dark.every((v, i) => v === light[i])) return one(dark, 'dark', ch);
    const dk = `var(${REGIME_VARS.dark},1)`;
    const lt = `var(${REGIME_VARS.light},0)`;
    return `calc(${dk}*(${channel(dark, ch, 'dark')}) + ${lt}*(${channel(light, ch, 'light')}))`;
  };
  return `rgb(${[0, 1, 2].map(both).join(' ')})`;
}

/** `row` for `seeds` as recolor() computes it: per channel ((a*bg + b*fg) + c*accent) + d, rounded half to even and clamped. */
export function rowHex(row: Row, seeds: Seeds): string {
  const [bg, fg, ac] = [seeds.bg, seeds.fg, seeds.accent].map(hexToRgb);
  const [a, b, c, ...d] = row;
  const ch = (i: number) => a * bg[i] + b * fg[i] + c * ac[i] + d[i];
  return rgbToHex(ch(0), ch(1), ch(2));
}

/** Index of the `>` closing the tag that starts at `open`, skipping quoted values. */
function tagEnd(svg: string, open: number): number {
  let quote = '';
  for (let i = open + 1; i < svg.length; i++) {
    const c = svg[i];
    if (quote) {
      if (c === quote) quote = '';
    } else if (c === '"' || c === "'") quote = c;
    else if (c === '>') return i;
  }
  throw new Error(`unclosed tag at ${open}`);
}

const ATTR_BEFORE = /([^\s=/>"']+)\s*=\s*(["'])\s*$/;
const MOTIF_TAG = /<g data-motif="" transform="([^"]*)">/;
const ROOT_TAG = /^<svg\b[^>]*>\n?/;
const DEFS = /^<defs>[\s\S]*?<\/defs>\n?/;

interface Edit {
  start: number;
  end: number;
  /** A declaration for the element's style attribute, replacing a presentation attribute. */
  decl?: string;
  /** Text replacing [start, end). */
  text?: string;
}

/**
 * `svg` with every slot that is not constant in every regime rewritten to `var(--c<k>)`: attribute
 * slots move into a `style` attribute on their element (merged with one already there), slots inside
 * `style` values are replaced in place. Returns the text, the rows of each k and whether any
 * rewritten slot lies before `defsEnd`.
 */
function slotsToVars(
  svg: string,
  entries: Partial<Record<Regime, EntryRows>>,
  defsEnd: number,
): { svg: string; vars: VarRows; inDefs: boolean } {
  const slots = findColors(svg);
  for (const [regime, e] of Object.entries(entries)) {
    if (slots.length !== e.n || e.occ.length !== slots.length)
      throw new Error(`${regime}: ${slots.length} color slots, slots.json says ${e.n}`);
  }
  const vars: VarRows = [];
  const index = new Map<string, number>();
  let inDefs = false;
  const tags = new Map<number, { end: number; edits: Edit[] }>();
  slots.forEach(([start, end], i) => {
    const pick = (e: EntryRows | undefined): [number | null, Row | null] => {
      if (!e) return [null, null];
      const r = e.occ[i];
      const row = e.coefs[r];
      if (!row) throw new Error(`slot ${i} names coefficient row ${r}, which is missing`);
      return [r, row];
    };
    const [d, dRow] = pick(entries.dark);
    const [l, lRow] = pick(entries.light);
    if ((!dRow || isConstant(dRow)) && (!lRow || isConstant(lRow))) return;
    const key = `${d}:${l}`;
    let k = index.get(key);
    if (k === undefined) {
      k = vars.length;
      vars.push([d, l]);
      index.set(key, k);
    }
    if (start < defsEnd) inDefs = true;
    const open = svg.lastIndexOf('<', start);
    let tag = tags.get(open);
    if (!tag) {
      tag = { end: tagEnd(svg, open), edits: [] };
      tags.set(open, tag);
    }
    const before = ATTR_BEFORE.exec(svg.slice(open, start));
    if (before && before[1] !== 'style') {
      // A presentation attribute cannot hold var(): drop it and restate it as a declaration.
      const close = svg.indexOf(before[2], end);
      tag.edits.push({
        start: open + before.index,
        end: close + 1,
        decl: `${before[1]}:var(--c${k})`,
      });
    } else {
      tag.edits.push({ start, end, text: `var(--c${k})` });
    }
  });
  let out = '';
  let last = 0;
  for (const [open, { end, edits }] of [...tags].sort((a, b) => a[0] - b[0])) {
    let tag = '';
    let at = open;
    const decls: string[] = [];
    for (const e of edits.sort((a, b) => a.start - b.start)) {
      tag += svg.slice(at, e.start);
      if (e.decl) {
        decls.push(e.decl);
        // The whitespace before a dropped attribute goes with it.
        tag = tag.replace(/\s+$/, '');
      } else tag += e.text;
      at = e.end;
    }
    tag += svg.slice(at, end + 1);
    if (decls.length) {
      const style = /\sstyle\s*=\s*(["'])([\s\S]*?)\1/.exec(tag);
      if (style) {
        const merged = `${style[2].replace(/;?\s*$/, '')};${decls.join(';')}`;
        tag = `${tag.slice(0, style.index)} style="${merged}"${tag.slice(style.index + style[0].length)}`;
      } else {
        tag = tag.replace(/\s*(\/?)>$/, ` style="${decls.join(';')}"$1>`);
      }
    }
    out += svg.slice(last, open) + tag;
    last = end + 1;
  }
  return { svg: out + svg.slice(last), vars, inDefs };
}

/** Every id the text declares. */
function ids(text: string): string[] {
  return [...text.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** `text` with the `id` attributes and `url(#…)`/`href="#…"` references of `names` renamed by `to`. */
function renameIds(text: string, names: readonly string[], to: (id: string) => string): string {
  if (!names.length) return text;
  const alt = names.map(escapeRe).join('|');
  return text
    .replace(new RegExp(`(\\sid=")(${alt})(")`, 'g'), (_, a, id, b) => `${a}${to(id)}${b}`)
    .replace(
      new RegExp(`(url\\(#|href="#)(${alt})([)"])`, 'g'),
      (_, a, id, b) => `${a}${to(id)}${b}`,
    );
}

export interface VarTemplate {
  /** The rewritten SVG text. */
  svg: string;
  /** The rows each `--c<k>` takes per regime; bake() needs them with the slots.json coefs. */
  vars: VarRows;
  /** Whether a slot inside `<defs>` reads the seeds. External `<use>` resolves paint servers in the file, out of reach of the page's variables, so such a template must be inlined in the page. */
  themedDefs: boolean;
  /** Whether the file has a motif part. */
  motif: boolean;
}

/**
 * The CSS-variable form of one build file, given the slots.json entry of each regime that uses it
 * and `hash`, the name it is served under. Throws when the slot count does not match an entry, or
 * the file is not the `<svg>` root, optional leading `<defs>`, content and optional trailing motif
 * group the build writes.
 */
export function toVarTemplate(
  svg: string,
  entries: Partial<Record<Regime, EntryRows>>,
  hash: string,
): VarTemplate {
  const root0 = ROOT_TAG.exec(svg);
  if (!root0) throw new Error('template has no <svg> root');
  const defs0 = DEFS.exec(svg.slice(root0[0].length));
  const defsEnd = defs0 ? root0[0].length + defs0[0].length : 0;
  const { svg: slotted, vars, inDefs } = slotsToVars(svg, entries, defsEnd);
  const root = ROOT_TAG.exec(slotted) as RegExpExecArray;
  const close = slotted.lastIndexOf('</svg>');
  const body = slotted.slice(root[0].length, close);
  const defs = DEFS.exec(body)?.[0] ?? '';
  const rest = body.slice(defs.length);
  const motif = MOTIF_TAG.exec(rest);
  const style = vars.length
    ? ` style="${vars
        .map(([d, l], k) => {
          const dark = d === null ? null : (entries.dark as EntryRows).coefs[d];
          const light = l === null ? null : (entries.light as EntryRows).coefs[l];
          return `--c${k}:${varColor(dark, light)}`;
        })
        .join(';')}"`
    : '';
  const ns = (id: string) => `t${hash}-${id}`;
  const defIds = ids(defs);
  const ground = motif ? rest.slice(0, motif.index) : rest;
  let out =
    `${root[0].replace(/\n?$/, '\n')}<g id="${partId(hash, 'base')}"${style}>\n` +
    renameIds(defs + ground, [...defIds, ...ids(ground)], ns) +
    '</g>\n';
  if (motif) {
    const inner = rest.slice(motif.index + motif[0].length, rest.lastIndexOf('</g>'));
    const used = defIds.filter((id) => inner.includes(`#${id})`) || inner.includes(`#${id}"`));
    const motifNs = (id: string) => ns(`${id}-m`);
    const ownDefs = used.length ? renameIds(defs, defIds, motifNs) : '';
    out +=
      `<g data-motif="" transform="${motif[1]}">\n<g id="${partId(hash, 'motif')}"${style}>\n` +
      `${ownDefs}${renameIds(renameIds(inner, used, motifNs), ids(inner), ns)}</g>\n</g>\n`;
  }
  out += '</svg>\n';
  return { svg: out, vars, themedDefs: inDefs, motif: Boolean(motif) };
}

const VAR_REF = /var\(--c(\d+)\)/g;
// A `--c<k>:rgb(...)` declaration; calc() nests var() and parentheses up to four levels deep.
const VAR_DEF =
  /--c\d+:rgb\((?:[^()]|\((?:[^()]|\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))*\))*\);?/g;

/** What bake() needs besides the text: the var rows and each regime's coefficient rows. */
export interface BakeRows {
  vars: VarRows;
  coefs: Partial<Record<Regime, readonly Row[]>>;
}

/**
 * A var template (toVarTemplate's text) as a standalone SVG for `seeds`, the colors recolor()
 * writes: every `var(--c<k>)` becomes the hex of its row in the seeds' regime and the variable
 * definitions go. With `place`, the motif group's transform is set to it. Throws when the template
 * does not serve the seeds' regime.
 */
export function bake(svg: string, rows: BakeRows, seeds: Seeds, place?: Placement): string {
  const regime = regimeOf(seeds);
  const coefs = rows.coefs[regime];
  if (!coefs) throw new Error(`the template has no ${regime} rows`);
  const hex = rows.vars.map(([d, l]) => {
    const r = regime === 'dark' ? d : l;
    if (r === null) throw new Error(`the template has no ${regime} rows`);
    return rowHex(coefs[r], seeds);
  });
  let out = svg
    .replace(VAR_DEF, '')
    .replace(/\sstyle=""/g, '')
    .replace(VAR_REF, (_, k: string) => hex[Number(k)]);
  if (place) out = out.replace(MOTIF_TAG, `<g data-motif="" transform="${motifTransform(place)}">`);
  return out;
}
