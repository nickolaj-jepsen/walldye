/**
 * Pure geometry and SVG rewriting for the detail page's crop window and export. Boxes are in
 * template canvas units; a crop is always of the 16:9 canvas.
 */
import { aspectLabel, CANVAS, DEFAULT_VARIANT, fileStem, SITE_ASPECTS, type Aspect } from '../lib/content';
import { shellWord } from '../lib/controls';

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Largest raster the browser can draw: canvas area and side limits shared by the engines. */
export const MAX_AREA = 16_777_216;
export const MAX_SIDE = 32_767;

const [W169, H169] = CANVAS['16:9'];

/** Width over height of an aspect such as "9:19.5". */
export function ratioOf(aspect: string): number {
  const [w, h] = aspect.split(':').map(Number);
  return w / h;
}

/** The axis a crop of 16:9 to `aspect` moves along: x for narrower shapes, y for wider ones. */
export function cropAxis(aspect: string): 'x' | 'y' {
  return ratioOf(aspect) < W169 / H169 ? 'x' : 'y';
}

/** Fraction of the 16:9 canvas the crop spans on its moving axis. */
export function cropSpan(aspect: string): number {
  const r = ratioOf(aspect) / (W169 / H169);
  return r < 1 ? r : 1 / r;
}

/** The crop of the 16:9 canvas to `aspect` at position `t` (0 = left or top edge, 1 = right or bottom), clamped. */
export function cropBox(aspect: string, t: number): Box {
  const p = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0.5));
  const r = ratioOf(aspect);
  if (cropAxis(aspect) === 'x') {
    const w = H169 * r;
    return { x: p * (W169 - w), y: 0, w, h: H169 };
  }
  const h = W169 / r;
  return { x: 0, y: p * (H169 - h), w: W169, h };
}

/** The position (rounded to the range input's 0.001 step) that centres the crop on `focus`, fractions of the canvas, clamped. */
export function focusPosition(aspect: string, focus: readonly [number, number]): number {
  const span = cropSpan(aspect);
  if (span >= 1) return 0.5;
  const f = cropAxis(aspect) === 'x' ? focus[0] : focus[1];
  const t = (f - span / 2) / (1 - span);
  return Math.round(Math.min(1, Math.max(0, t)) * 1000) / 1000;
}

/** The largest box of width/height `ratio` inside `box`, centred in it. */
export function fitRect(box: Box, ratio: number): Box {
  if (box.w / box.h > ratio) {
    const w = box.h * ratio;
    return { x: box.x + (box.w - w) / 2, y: box.y, w, h: box.h };
  }
  const h = box.w / ratio;
  return { x: box.x, y: box.y + (box.h - h) / 2, w: box.w, h };
}

/** `n` with at most `places` decimals and no trailing zeros. */
export function num(n: number, places = 4): string {
  const s = n.toFixed(places);
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s;
}

function setAttr(tag: string, name: string, value: string): string {
  const re = new RegExp(`(\\s${name}\\s*=\\s*)(?:"[^"]*"|'[^']*')`);
  if (re.test(tag)) return tag.replace(re, (_, lead: string) => `${lead}"${value}"`);
  return tag.replace(/\s*(\/?)>$/, (_, slash: string) => ` ${name}="${value}"${slash}>`);
}

/**
 * `svg` with its root element's viewBox set to `box`, width and height to `width` and `height`, and
 * preserveAspectRatio to `preserve` when given. Returns `svg` unchanged when it has no root <svg> tag.
 */
export function setRoot(svg: string, box: Box, width: number, height: number, preserve?: string): string {
  const m = /<svg\b[^>]*>/.exec(svg);
  if (!m) return svg;
  let tag = setAttr(m[0], 'viewBox', [box.x, box.y, box.w, box.h].map((v) => num(v)).join(' '));
  tag = setAttr(tag, 'width', num(width));
  tag = setAttr(tag, 'height', num(height));
  if (preserve) tag = setAttr(tag, 'preserveAspectRatio', preserve);
  return svg.slice(0, m.index) + tag + svg.slice(m.index + m[0].length);
}

/** `svg` with `shape-rendering="crispEdges"` on every <path> whose class list has `px` and that sets no shape-rendering. */
export function crispPixels(svg: string): string {
  return svg.replace(/<path\b[^>]*>/g, (tag) =>
    /\sclass\s*=\s*"(?:[^"]*\s)?px(?:\s[^"]*)?"/.test(tag) && !/\sshape-rendering\s*=/.test(tag) ? `<path shape-rendering="crispEdges"${tag.slice(5)}` : tag,
  );
}

function xmlText(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** `svg` with `<title>` and `<desc>` as the root element's first children. */
export function withTitle(svg: string, title: string, desc: string): string {
  const m = /<svg\b[^>]*>/.exec(svg);
  if (!m) return svg;
  const at = m.index + m[0].length;
  return `${svg.slice(0, at)}<title>${xmlText(title)}</title><desc>${xmlText(desc)}</desc>${svg.slice(at)}`;
}

/** The site aspect closest to `width`×`height` by |log ratio| (the first on a tie). */
export function nearestAspect(width: number, height: number): Aspect {
  const r = Math.log(width / height);
  let best: Aspect = SITE_ASPECTS[0];
  let gap = Infinity;
  for (const a of SITE_ASPECTS) {
    const d = Math.abs(r - Math.log(ratioOf(a)));
    if (d < gap - 1e-12) [best, gap] = [a, d];
  }
  return best;
}

/** Whether a `width`×`height` raster fits the browser limits (MAX_AREA, MAX_SIDE). */
export function withinLimits(width: number, height: number): boolean {
  return width * height <= MAX_AREA && width <= MAX_SIDE && height <= MAX_SIDE;
}

/**
 * The narrowest and widest whole pixel widths that grid cells of `cells` canvas units take at
 * `scale` pixels per unit, or null when every cell lands on a whole number of pixels.
 */
export function cellWidths(cells: readonly number[], scale: number): [number, number] | null {
  const px = cells.map((c) => c * scale);
  if (px.every((w) => Math.abs(w - Math.round(w)) < 1e-6)) return null;
  return [Math.min(...px.map(Math.floor)), Math.max(...px.map(Math.ceil))];
}

/** Everything that shapes one export's geometry. */
export interface ExportShape {
  /** Selected shape, like "16:10". */
  aspect: string;
  /** Whether the piece has its own template for `aspect`; otherwise it is a crop of 16:9. */
  native: boolean;
  /** Crop position, used only when not native. */
  t: number;
}

/** The template aspect an export reads and the box of that canvas it shows. */
export function sourceBox(shape: ExportShape): { aspect: string; box: Box } {
  if (shape.native) {
    const [w, h] = CANVAS[shape.aspect as Aspect];
    return { aspect: shape.aspect, box: { x: 0, y: 0, w, h } };
  }
  return { aspect: '16:9', box: cropBox(shape.aspect, shape.t) };
}

/** The recoloured SVG as an SVG download: cut to the shape's box at its canvas size, titled. */
export function svgExport(svg: string, shape: ExportShape, title: string, desc: string): string {
  const { box } = sourceBox(shape);
  return withTitle(setRoot(svg, box, box.w, box.h), title, desc);
}

/** Pixels per canvas unit when `shape` is exported at `width`×`height`. */
export function exportScale(shape: ExportShape, width: number, height: number): number {
  return width / fitRect(sourceBox(shape).box, width / height).w;
}

/**
 * The recoloured SVG prepared for rasterising at exactly `width`×`height` (the viewBox is the largest
 * box of that ratio inside the shape's box, sliced to fill), and `scale`, pixels per canvas unit.
 */
export function rasterSvg(svg: string, shape: ExportShape, width: number, height: number): { svg: string; scale: number } {
  const rect = fitRect(sourceBox(shape).box, width / height);
  return { svg: setRoot(svg, rect, width, height, 'xMidYMid slice'), scale: width / rect.w };
}

/**
 * The `uv run walldye render` command for this version, shape and crop, with a `--set` per item of
 * `sets` (`k=v`) and `edits` after the stem of the output name; `--variant` only for a named variant.
 * It draws the same picture as the SVG download; the file differs in the crop's rounding (3 decimals
 * here, 4 in the download) and has no `<title>`/`<desc>`.
 */
export function renderCommand(slug: string, variant: string, token: string, shape: ExportShape, sets: readonly string[] = [], edits = ''): string {
  const parts = ['uv run walldye render', slug];
  if (variant !== DEFAULT_VARIANT) parts.push('--variant', variant);
  for (const s of sets) parts.push('--set', shellWord(s));
  parts.push('--theme', token);
  if (shape.native && shape.aspect !== '16:9') parts.push('--aspect', shape.aspect);
  if (!shape.native) {
    const b = cropBox(shape.aspect, shape.t);
    parts.push('--crop', [b.x, b.y, b.w, b.h].map((v) => num(v, 3)).join(','));
  }
  parts.push('-o', `${fileStem(slug, variant)}${edits}-${token}-${aspectLabel(shape.aspect)}${shape.native ? '' : '-crop'}.svg`);
  return parts.join(' ');
}
