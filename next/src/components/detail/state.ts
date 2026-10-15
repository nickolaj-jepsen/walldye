/**
 * The detail page's state and the pure rules between it, the address and the export choices. The
 * address holds `v` (the version, left out for the default), `shape` (e.g. `16x10`), `crop` (0..1,
 * only once the visitor placed it on a cropped shape), and for a piece with a motif `at` (`x,y` in
 * canvas units) and `size`, each only once the visitor moved or resized it.
 */
import {
  type Aspect,
  aspectLabel,
  aspectOfLabel,
  CANVAS,
  DEFAULT_SIZE_INDEX,
  EXPORT_SIZES,
} from '../../lib/content';
import { clampPlacement, type MotifInfo, num, type Placement } from '../../lib/motif';
import { type Box, cropAxis, cropSpan, type ExportShape, focusPosition } from '../../lib/shape';

export interface DetailState {
  variant: string;
  aspect: Aspect;
  /** Crop position the visitor placed (range, drag or `?crop=`); null follows the version's focus. */
  crop: number | null;
  /** Where the visitor put the motif's anchor, canvas units; null keeps the design's. */
  at: [number, number] | null;
  /** The motif's size the visitor chose; null keeps the drawn size. */
  scale: number | null;
}

/** The shapes the piece has its own template for; every other shape is a crop of 16:9. */
export type Native = ReadonlySet<string>;

/** `?shape=`: an Aspect from its label, such as `16x10`. */
export function parseShape(raw: string): Aspect | null {
  return aspectOfLabel(raw) ?? null;
}

export function writeShape(aspect: Aspect): string {
  return aspectLabel(aspect);
}

/** `?crop=`: a plain decimal in 0..1, else null. Number() alone would take "0x1" and "", parseFloat "0.9junk". */
export function parseCrop(raw: string): number | null {
  const crop = /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(raw) ? Number(raw) : Number.NaN;
  return crop >= 0 && crop <= 1 ? crop : null;
}

export function writeCrop(t: number): string {
  return num(t, 3);
}

/** `?at=`: two whole canvas units, `x,y`, else null. */
export function parseAt(raw: string): [number, number] | null {
  const at = /^(\d{1,5}),(\d{1,5})$/.exec(raw);
  return at ? [Number(at[1]), Number(at[2])] : null;
}

export function writeAt(at: readonly [number, number]): string {
  return at.join(',');
}

/** `?size=`: a positive size under 10 with at most 4 decimals, else null. */
export function parseScale(raw: string): number | null {
  return /^\d(?:\.\d{1,4})?$/.test(raw) && Number(raw) > 0 ? Number(raw) : null;
}

export function writeScale(k: number): string {
  return num(k, 4);
}

/** Where `s` puts the motif `info` describes, as the site offers it; null while the visitor has not moved or resized it. */
export function placementOf(s: DetailState, info: MotifInfo | undefined): Placement | null {
  if (!info || (s.at === null && s.scale === null)) return null;
  const [w, h] = CANVAS[s.aspect];
  const [x, y] = s.at ?? info.at;
  return clampPlacement(info, w, h, { x, y, k: s.scale ?? 1 });
}

/** The export geometry of `s`: an unplaced crop centered on `focus` (fractions of the canvas), and the motif `info` placed. */
export function shapeOf(
  s: DetailState,
  native: Native,
  focus: readonly [number, number],
  info?: MotifInfo,
): ExportShape {
  return {
    aspect: s.aspect,
    native: native.has(s.aspect),
    t: s.crop ?? focusPosition(s.aspect, focus),
    place: placementOf(s, info),
  };
}

/** The placed crop after a change of shape: kept only while both shapes crop along the same axis. */
export function keptCrop(s: DetailState, next: Aspect, native: Native): number | null {
  const sameAxis =
    !native.has(s.aspect) && !native.has(next) && cropAxis(s.aspect) === cropAxis(next);
  return sameAxis ? s.crop : null;
}

/**
 * The size to select for `aspect`: `keep` when that shape offers it and `allowed` passes it, else the
 * default size, else the first allowed one, else the smallest.
 */
export function sizeFor(aspect: Aspect, keep: string, allowed: (size: string) => boolean): string {
  const list = EXPORT_SIZES[aspect];
  const options = [...list, 'screen'];
  if (options.includes(keep) && allowed(keep)) return keep;
  return [list[DEFAULT_SIZE_INDEX], ...options].find(allowed) ?? list[0];
}

/** Output pixels of a size radio's value; `screen` is the screen's own, `screenPx`. */
export function sizePx(size: string, screenPx: readonly [number, number]): [number, number] {
  if (size === 'screen') return [screenPx[0], screenPx[1]];
  const [w, h] = size.split('x').map(Number);
  return [w, h];
}

/** Whether `aspect` is taller than wide. */
export function isTall(aspect: Aspect): boolean {
  const [w, h] = CANVAS[aspect];
  return h > w;
}

/** Whether the plate shows `shape`'s crop itself: narrow screens, tall shapes cropped from 16:9. */
export function cropsInPlace(
  shape: Pick<ExportShape, 'aspect' | 'native'>,
  narrow: boolean,
): boolean {
  return narrow && !shape.native && isTall(shape.aspect);
}

/** The crop window's box over the 16:9 picture for `shape`, as CSS; heights are fractions of the picture's, not the rounded plate's. */
export function cropWindowStyle(shape: Pick<ExportShape, 'aspect' | 't'>): {
  left: string;
  top: string;
  width: string;
  height: string;
} {
  const span = cropSpan(shape.aspect);
  const offset = shape.t * (1 - span);
  const tall = (f: number) => `calc(${f} * 100cqw / var(--ratio))`;
  return cropAxis(shape.aspect) === 'x'
    ? { left: `${offset * 100}%`, width: `${span * 100}%`, top: '0', height: tall(1) }
    : { left: '0', width: '100%', top: tall(offset), height: tall(span) };
}

/**
 * Where a `w`×`h` canvas lies in a frame of width/height `ratio` that shows its `view` centered and
 * whole (an `<svg>`'s default preserveAspectRatio), in percentages of the frame. Parts of the canvas
 * outside the view fall outside 0..100%.
 */
export function canvasRect(
  view: Box,
  w: number,
  h: number,
  ratio: number,
): { left: string; top: string; width: string; height: string } {
  // Frame units: width 1, height 1 / ratio.
  const s = Math.min(1 / view.w, 1 / ratio / view.h);
  const x = (1 - view.w * s) / 2 - view.x * s;
  const y = (1 / ratio - view.h * s) / 2 - view.y * s;
  const pct = (v: number) => `${num(v * 100, 4)}%`;
  return { left: pct(x), top: pct(y * ratio), width: pct(w * s), height: pct(h * s * ratio) };
}

/** `box` (canvas units) over a `w`×`h` canvas, in percentages of the canvas. */
export function boxStyle(
  box: readonly number[],
  w: number,
  h: number,
): { left: string; top: string; width: string; height: string } {
  const pct = (v: number) => `${num(v * 100, 4)}%`;
  return {
    left: pct(box[0] / w),
    top: pct(box[1] / h),
    width: pct(box[2] / w),
    height: pct(box[3] / h),
  };
}

/**
 * The CSS transform that shows a motif drawn at `from` as if placed at `to`: the motif layer's
 * wrapper sits outside the `<g>` holding `from`'s translate and scale, and SVG takes px as user units.
 */
export function motifShift(from: Placement, to: Placement): string {
  const r = to.k / from.k;
  return `translate(${num(to.x, 2)}px, ${num(to.y, 2)}px) scale(${num(r, 6)}) translate(${num(-from.x, 2)}px, ${num(-from.y, 2)}px)`;
}
