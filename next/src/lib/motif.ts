/**
 * A template's motif, the one thing a visitor may move and resize: a port of walldye/tools/motif.py
 * (transform, place, ground, alone) plus the placements the site offers. Boxes are [x, y, w, h];
 * `extent`, `handle` and windows are in motif-local units, anchors in canvas units.
 */

/** A slots.json entry's `motif`, as the build writes it. */
export interface MotifInfo {
  /** Where the design drew the anchor, canvas units. */
  at: [number, number];
  /** Every mark the motif draws; with `overscan`, the whole area any placement can show. */
  extent: [number, number, number, number];
  /** What a visitor grabs to move it. */
  handle: [number, number, number, number];
  overscan: boolean;
  /** The pixel cell sizes keep whole, a whole number of units, or null. */
  cell: number | null;
  /** The sizes offered, [lo, hi]. */
  scale: [number, number];
}

/** Anchor (x, y) in canvas units and size k. */
export interface Placement {
  x: number;
  y: number;
  k: number;
}

const TAG = /<g data-motif="" transform="([^"]*)">/;
const ROOT = /^<svg\b[^>]*>\n/;

/** `n` with at most `places` decimals, no trailing zeros, and -0 as 0, as walldye's fmt() writes it. */
export function num(n: number, places = 4): string {
  const s = n.toFixed(places);
  const t = s.includes('.') ? s.replace(/\.?0+$/, '') : s;
  return t === '-0' ? '0' : t;
}

/** The motif group's transform: translate(x y), then scale(k) unless k is 1. */
export function motifTransform(p: Placement): string {
  const head = `translate(${num(p.x, 2)} ${num(p.y, 2)})`;
  return p.k === 1 ? head : `${head} scale(${num(p.k, 4)})`;
}

/** `svg` with its motif placed at `p`; `svg` itself when it has no motif. */
export function placeMotif(svg: string, p: Placement): string {
  return svg.replace(TAG, `<g data-motif="" transform="${motifTransform(p)}">`);
}

/** `svg` without its motif group, the root's last child; `svg` itself when it has none. */
export function motifGround(svg: string): string {
  const m = TAG.exec(svg);
  return m ? `${svg.slice(0, m.index)}</svg>\n` : svg;
}

/**
 * The motif of `svg` on its own: the root showing the motif-local `box`, the template's <defs> and
 * the motif group untransformed. Throws when `svg` has no motif.
 */
export function motifAlone(svg: string, box: readonly number[]): string {
  const root = ROOT.exec(svg);
  const m = TAG.exec(svg);
  if (!root || !m) throw new Error('the SVG has no motif to cut out');
  const rest = svg.slice(root[0].length);
  const defs = /^<defs>[\s\S]*?<\/defs>\n/.exec(rest)?.[0] ?? '';
  const [x, y, w, h] = box.map((v) => num(v, 2));
  const head = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${x} ${y} ${w} ${h}" width="${w}" height="${h}">\n`;
  const body = svg.slice(m.index + m[0].length, svg.lastIndexOf('</svg>'));
  return `${head}${defs}<g data-motif="">${body}</svg>\n`;
}

/** The size nearest `k` the site offers: within the motif's scale, whole cells at 4 decimals, else 2 decimals. */
export function motifSize(info: MotifInfo, k: number): number {
  const [lo, hi] = info.scale;
  const c = Math.min(hi, Math.max(lo, Number.isFinite(k) ? k : 1));
  if (!info.cell) return Math.round(c * 100) / 100;
  const n = Math.min(
    Math.floor(hi * info.cell + 1e-9),
    Math.max(Math.ceil(lo * info.cell - 1e-9), Math.floor(c * info.cell + 0.5)),
  );
  return Math.round((n / info.cell) * 10_000) / 10_000;
}

/** The placement nearest `p` the site offers on a `w`×`h` canvas: the anchor in whole units on the canvas, the size as motifSize(). */
export function clampPlacement(info: MotifInfo, w: number, h: number, p: Placement): Placement {
  const whole = (v: number, max: number) => Math.min(max, Math.max(0, Math.round(v)));
  return { x: whole(p.x, w), y: whole(p.y, h), k: motifSize(info, p.k) };
}

/** Whether a visitor could make `p` on a `w`×`h` canvas: walldye render --place accepts the same. */
export function allowedPlacement(info: MotifInfo, w: number, h: number, p: Placement): boolean {
  const [lo, hi] = info.scale;
  const onCanvas = p.x >= 0 && p.x <= w && p.y >= 0 && p.y <= h;
  // A size written to 4 decimals is up to 5e-5 off the one meant, so cells are up to cell * 5e-5 off whole.
  const cells =
    info.cell === null ||
    Math.abs(info.cell * p.k - Math.round(info.cell * p.k)) <= info.cell * 5e-5 + 1e-9;
  return onCanvas && p.k >= lo && p.k <= hi && cells;
}

/** Where the design drew the motif. */
export function drawnPlacement(info: MotifInfo): Placement {
  return { x: info.at[0], y: info.at[1], k: 1 };
}

/** `box` (motif-local) as canvas units under `p`. */
export function placedBox(box: readonly number[], p: Placement): [number, number, number, number] {
  return [p.x + box[0] * p.k, p.y + box[1] * p.k, box[2] * p.k, box[3] * p.k];
}

/**
 * The motif-local box a live layer draws for `p` on a `w`×`h` canvas: the extent, or for an overscan
 * motif the canvas grown by `margin` of its size on every side, mapped back into motif units and
 * kept within the extent.
 */
export function motifWindow(
  info: MotifInfo,
  w: number,
  h: number,
  p: Placement,
  margin = 0.25,
): [number, number, number, number] {
  if (!info.overscan) return [...info.extent];
  const [ex, ey, ew, eh] = info.extent;
  const x0 = Math.max(ex, (-margin * w - p.x) / p.k);
  const y0 = Math.max(ey, (-margin * h - p.y) / p.k);
  const x1 = Math.min(ex + ew, ((1 + margin) * w - p.x) / p.k);
  const y1 = Math.min(ey + eh, ((1 + margin) * h - p.y) / p.k);
  return [x0, y0, Math.max(0, x1 - x0), Math.max(0, y1 - y0)];
}

/** `p` with the handle's middle on the middle of a `w`×`h` canvas along `axis`, as clampPlacement() offers it. */
export function centerMotif(
  info: MotifInfo,
  w: number,
  h: number,
  p: Placement,
  axis: 'x' | 'y',
): Placement {
  const [hx, hy, hw, hh] = info.handle;
  const to = axis === 'x' ? w / 2 - (hx + hw / 2) * p.k : h / 2 - (hy + hh / 2) * p.k;
  return clampPlacement(info, w, h, { ...p, [axis]: to });
}

/**
 * The placement nearest `from` resized by its handle's `corner` ([0|1, 0|1], left/top to right/bottom)
 * dragged to the canvas point `to`, as clampPlacement() offers it: the opposite corner stays put and
 * the size follows `to` projected onto the handle's diagonal.
 */
export function resizeMotif(
  info: MotifInfo,
  w: number,
  h: number,
  from: Placement,
  corner: readonly [number, number],
  to: readonly [number, number],
): Placement {
  const [hx, hy, hw, hh] = info.handle;
  // The fixed corner, motif-local and on the canvas, and the local diagonal towards the dragged one.
  const fx = hx + (1 - corner[0]) * hw;
  const fy = hy + (1 - corner[1]) * hh;
  const [cx, cy] = [from.x + fx * from.k, from.y + fy * from.k];
  const [dx, dy] = [(corner[0] * 2 - 1) * hw, (corner[1] * 2 - 1) * hh];
  const k = motifSize(info, ((to[0] - cx) * dx + (to[1] - cy) * dy) / (dx * dx + dy * dy));
  return clampPlacement(info, w, h, { x: cx - fx * k, y: cy - fy * k, k });
}

/**
 * The placement nearest `from` after a pinch that began at midpoint `m0` with the fingers `d0` apart
 * and is now at `m`, `d` apart (canvas units), as clampPlacement() offers it: the size follows d/d0,
 * and the motif's point under `m0` follows the midpoint.
 */
export function pinchMotif(
  info: MotifInfo,
  w: number,
  h: number,
  from: Placement,
  m0: readonly [number, number],
  d0: number,
  m: readonly [number, number],
  d: number,
): Placement {
  const k = motifSize(info, d0 > 0 ? (from.k * d) / d0 : from.k);
  const r = k / from.k;
  return clampPlacement(info, w, h, {
    x: m[0] + (from.x - m0[0]) * r,
    y: m[1] + (from.y - m0[1]) * r,
    k,
  });
}
