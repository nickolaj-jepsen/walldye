/**
 * The site icon: a 4 by 4 grid of seed mixes, bg at the top left, fg at the top right and accent at the
 * bottom left. The static /favicon.svg and the theme boot's live icon both draw it from here.
 */

import { hexToRgb, rgbToHex, type Seeds } from './theme';

const N = 4;
const CELL = 8;

/** Each cell's [bg, fg, accent] weights, summing to 1, row by row from the top left. */
function faviconWeights(): [number, number, number][] {
  const out: [number, number, number][] = [];
  for (let r = 0; r < N; r++) {
    for (let c = 0; c < N; c++) {
      const u = c / (N - 1);
      const v = r / (N - 1);
      // Halving the cross terms keeps the bottom-right cell a fg/accent blend with no bg in it.
      const fg = u * (1 - v / 2);
      const accent = v * (1 - u / 2);
      out.push([1 - fg - accent, fg, accent]);
    }
  }
  return out;
}

/** The cells' colors for `seeds`, row by row from the top left. */
export function faviconColors(seeds: Seeds): string[] {
  const [b, f, a] = [seeds.bg, seeds.fg, seeds.accent].map(hexToRgb);
  return faviconWeights().map(([wb, wf, wa]) => {
    const channel = (i: number) => wb * b[i] + wf * f[i] + wa * a[i];
    return rgbToHex(channel(0), channel(1), channel(2));
  });
}

/**
 * The icon as SVG source in `seeds`. With `light`, the cells take their fills from a style block that
 * switches to `light` under `prefers-color-scheme: light`, as site.css does without JavaScript.
 */
export function faviconSvg(seeds: Seeds, light?: Seeds): string {
  const size = N * CELL;
  const dark = faviconColors(seeds);
  const cells = dark.map((fill, i) => {
    const x = (i % N) * CELL;
    const y = Math.floor(i / N) * CELL;
    const paint = light ? `class="c${i}"` : `fill="${fill}"`;
    return `<rect x="${x}" y="${y}" width="${CELL}" height="${CELL}" ${paint}/>`;
  });
  const rules = (fills: string[]) => fills.map((f, i) => `.c${i}{fill:${f}}`).join('');
  const style = light
    ? `<style>${rules(dark)}@media (prefers-color-scheme: light){${rules(faviconColors(light))}}</style>`
    : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges">${style}${cells.join('')}</svg>`;
}

/** faviconSvg(seeds) as a `data:` URL for `<link rel="icon">`. */
export function faviconUrl(seeds: Seeds): string {
  return `data:image/svg+xml,${encodeURIComponent(faviconSvg(seeds))}`;
}
