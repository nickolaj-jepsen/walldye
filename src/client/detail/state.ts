/**
 * The detail page's state and the pure rules between it, the address and the export panel. The
 * address holds `v` (the version, left out for the default), `shape` (e.g. `16x10`, left out for 16:9)
 * and `crop` (0..1, only once the visitor placed it on a cropped shape).
 */
import {
  type Aspect,
  aspectLabel,
  DEFAULT_SIZE_INDEX,
  DEFAULT_VARIANT,
  EXPORT_SIZES,
  isAspect,
} from '../../lib/content';
import { cropAxis, type ExportShape, focusPosition, num } from '../export/shape';

export interface DetailState {
  variant: string;
  aspect: Aspect;
  /** Crop position the visitor placed (range, drag or `?crop=`); null follows the version's focus. */
  crop: number | null;
  /** The size radio's value: `<w>x<h>` or `screen`. */
  size: string;
}

/** The shapes the piece has its own template for; every other shape is a crop of 16:9. */
export type Native = ReadonlySet<string>;

/** What the address asks for: each field only when it is well formed. */
export function readAddress(
  params: URLSearchParams,
): Partial<Pick<DetailState, 'variant' | 'aspect' | 'crop'>> {
  const out: Partial<DetailState> = {};
  const v = params.get('v');
  if (v) out.variant = v;
  const shape = params.get('shape')?.replace('x', ':');
  if (isAspect(shape)) out.aspect = shape;
  // Only a plain decimal: Number() alone would take "0x1" and "", parseFloat "0.9junk".
  const raw = params.get('crop') ?? '';
  const crop = /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(raw) ? Number(raw) : Number.NaN;
  if (crop >= 0 && crop <= 1) out.crop = crop;
  return out;
}

/** `url` with `v`, `shape` and `crop` set for `s`, each left out at its default. */
export function writeAddress(url: URL, s: DetailState, native: Native): URL {
  const out = new URL(url);
  for (const key of ['v', 'shape', 'crop']) out.searchParams.delete(key);
  if (s.variant !== DEFAULT_VARIANT) out.searchParams.set('v', s.variant);
  if (s.aspect !== '16:9') out.searchParams.set('shape', aspectLabel(s.aspect));
  if (!native.has(s.aspect) && s.crop !== null) out.searchParams.set('crop', num(s.crop, 3));
  return out;
}

/** The export geometry of `s`, an unplaced crop centred on `focus` (fractions of the canvas). */
export function shapeOf(
  s: DetailState,
  native: Native,
  focus: readonly [number, number],
): ExportShape {
  return {
    aspect: s.aspect,
    native: native.has(s.aspect),
    t: s.crop ?? focusPosition(s.aspect, focus),
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
