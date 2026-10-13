/**
 * The detail page's state and the pure rules between it, the address and the export panel. The
 * address holds `v` (the version, left out for the default), `shape` (e.g. `16x10`, left out for 16:9),
 * `crop` (0..1, only once the visitor placed it on a cropped shape), and for a piece with a motif `at`
 * (`x,y` in canvas units) and `size`, each only once the visitor moved or resized it.
 */
import {
  type Aspect,
  aspectLabel,
  aspectOfLabel,
  CANVAS,
  DEFAULT_SIZE_INDEX,
  DEFAULT_VARIANT,
  EXPORT_SIZES,
} from '../../lib/content';
import { clampPlacement, type MotifInfo, type Placement } from '../../lib/motif';
import { cropAxis, type ExportShape, focusPosition, num } from '../../lib/shape';

export interface DetailState {
  variant: string;
  aspect: Aspect;
  /** Crop position the visitor placed (range, drag or `?crop=`); null follows the version's focus. */
  crop: number | null;
  /** The size radio's value: `<w>x<h>` or `screen`. */
  size: string;
  /** Where the visitor put the motif's anchor, canvas units; null keeps the design's. */
  at: [number, number] | null;
  /** The motif's size the visitor chose; null keeps the drawn size. */
  scale: number | null;
}

/** The shapes the piece has its own template for; every other shape is a crop of 16:9. */
export type Native = ReadonlySet<string>;

/** What the address asks for: each field only when it is well formed. */
export function readAddress(
  params: URLSearchParams,
): Partial<Pick<DetailState, 'variant' | 'aspect' | 'crop' | 'at' | 'scale'>> {
  const out: Partial<DetailState> = {};
  const v = params.get('v');
  if (v) out.variant = v;
  const shape = aspectOfLabel(params.get('shape'));
  if (shape) out.aspect = shape;
  // Only a plain decimal: Number() alone would take "0x1" and "", parseFloat "0.9junk".
  const raw = params.get('crop') ?? '';
  const crop = /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(raw) ? Number(raw) : Number.NaN;
  if (crop >= 0 && crop <= 1) out.crop = crop;
  const at = /^(\d{1,5}),(\d{1,5})$/.exec(params.get('at') ?? '');
  if (at) out.at = [Number(at[1]), Number(at[2])];
  const size = params.get('size') ?? '';
  if (/^\d(?:\.\d{1,4})?$/.test(size) && Number(size) > 0) out.scale = Number(size);
  return out;
}

/** `url` with `v`, `shape`, `crop`, `at` and `size` set for `s`, each left out at its default. */
export function writeAddress(url: URL, s: DetailState, native: Native): URL {
  const out = new URL(url);
  for (const key of ['v', 'shape', 'crop', 'at', 'size']) out.searchParams.delete(key);
  if (s.variant !== DEFAULT_VARIANT) out.searchParams.set('v', s.variant);
  if (s.aspect !== '16:9') out.searchParams.set('shape', aspectLabel(s.aspect));
  if (!native.has(s.aspect) && s.crop !== null) out.searchParams.set('crop', num(s.crop, 3));
  if (s.at) out.searchParams.set('at', s.at.join(','));
  if (s.scale !== null) out.searchParams.set('size', num(s.scale, 4));
  return out;
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
