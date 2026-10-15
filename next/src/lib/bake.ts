/**
 * The files the export makes from a var template: its colors baked to the hex recolor() writes for the
 * seeds, pixel-art paths crisp, the motif placed and the shape's box cut. Pure, so it runs anywhere,
 * but it pulls in the tokenizer: keep it out of everything but the export and build-time code.
 */
import { DEFAULT_VARIANT } from './content';
import { crispPixels, type ExportShape, rasterSvg, svgExport } from './shape';
import { type BakeRows, bake } from './template-vars';
import { regimeOf, type Seeds } from './theme';

/** One var template's text and rows, and the seeds to bake it for. */
export interface BakeSource {
  /** The text of `/t/<hash>.svg`. */
  template: string;
  rows: BakeRows;
  seeds: Seeds;
}

/**
 * The template for the seeds as a standalone SVG at its own canvas, the motif where it was drawn.
 * Paths of class `px` get crispEdges, which only pixel-art pieces draw. Throws when the template does
 * not serve the seeds' regime.
 */
export function bakedSvg(src: BakeSource): string {
  return crispPixels(bake(src.template, src.rows, src.seeds));
}

/** The SVG download: baked, the motif placed, cut to the shape's box at its canvas size, titled. */
export function svgFile(src: BakeSource, shape: ExportShape, title: string, desc: string): string {
  return svgExport(bakedSvg(src), shape, title, desc);
}

/** The SVG to rasterize at exactly `width`×`height`: baked, the motif placed, sliced to fill. */
export function rasterFile(
  src: BakeSource,
  shape: ExportShape,
  width: number,
  height: number,
): string {
  return rasterSvg(bakedSvg(src), shape, width, height).svg;
}

/** Which of a plate's two templates the seeds read: the dark or the light one by their regime. */
export function regimeTemplate<T>(plate: { dark: T; light: T }, seeds: Seeds): T {
  return plate[regimeOf(seeds)];
}

/**
 * The `<desc>` of an SVG download: the page `address` (host and path, `?v=` added for a named
 * variant), the license when there is one, and the theme token, joined by middle dots.
 */
export function aboutLine(
  address: string,
  variant: string,
  license: string,
  token: string,
): string {
  const at = variant === DEFAULT_VARIANT ? address : `${address}?v=${variant}`;
  return [at, license, `theme ${token}`].filter(Boolean).join(' · ');
}
