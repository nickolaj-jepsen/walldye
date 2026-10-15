import { describe, expect, it } from 'vitest';
import { aboutLine, bakedSvg, rasterFile, regimeTemplate, svgFile } from './bake';
import { recolor, type SlotsEntry } from './recolor';
import type { ExportShape } from './shape';
import { type BakeRows, toVarTemplate } from './template-vars';
import { parseToken, type Seeds } from './theme';
import { findColors } from './tokenize';

// Slots in order: two stops, the ground, a pixel path, the motif's stroke.
const SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">
<defs><linearGradient id="g"><stop offset="0" stop-color="#1c1b1a"/><stop offset="1" stop-color="#cecdc3"/></linearGradient></defs>
<rect width="1920" height="1080" fill="#1c1b1a"/>
<path class="px" d="M0 0h10v10h-10z" fill="#d14d41"/>
<g data-motif="" transform="translate(960 540)">
<circle r="100" fill="url(#g)" stroke="#75736c"/>
</g>
</svg>
`;

const entry = (coefs: number[][]): SlotsEntry => ({
  file: '16x9.svg',
  sha256: '0'.repeat(64),
  n: 5,
  coefs,
  occ: [0, 1, 0, 2, 3],
});
const DARK = entry([
  [1, 0, 0, 0, 0, 0],
  [0, 1, 0, 0, 0, 0],
  [0, 0, 1, 0, 0, 0],
  [0.5, 0.5, 0, 0, 0, 0],
]);
const LIGHT = entry([
  [1, 0, 0, 0, 0, 0],
  [0, 0.9, 0, 10, 10, 10],
  [0, 0, 1, 0, 0, 0],
  [0.25, 0.75, 0, 0, 0, 0],
]);

const HASH = 'abcdef012345';
const v = toVarTemplate(SVG, { dark: DARK, light: LIGHT }, HASH);
const rows: BakeRows = { vars: v.vars, coefs: { dark: DARK.coefs, light: LIGHT.coefs } };

const seeds = (token: string): Seeds => parseToken(token) as Seeds;
const colors = (svg: string) => new Set(findColors(svg).map(([s, e]) => svg.slice(s, e)));
const NATIVE: ExportShape = { aspect: '16:9', native: true, t: 0.5 };

describe('bakedSvg', () => {
  it.each([
    ['1a1b26-c0caf5-ff9e64', DARK],
    ['f4ecd8-3b2f2f-b5452a', LIGHT],
  ])('writes the colors recolor() writes for %s', (token, e) => {
    const s = seeds(token);
    const baked = bakedSvg({ template: v.svg, rows, seeds: s });
    expect(baked).not.toMatch(/var\(|--c\d/);
    expect(colors(baked)).toEqual(colors(recolor(SVG, e, s)));
  });

  it('makes only pixel paths crisp', () => {
    const baked = bakedSvg({ template: v.svg, rows, seeds: seeds('fireproof') });
    expect(baked.match(/crispEdges/g)).toHaveLength(1);
    expect(baked).toMatch(/<path shape-rendering="crispEdges" class="px"/);
  });
});

describe('svgFile', () => {
  const src = { template: v.svg, rows, seeds: seeds('1a1b26-c0caf5-ff9e64') };

  it('places the motif and titles the file', () => {
    const out = svgFile(src, { ...NATIVE, place: { x: 100, y: 200, k: 1.5 } }, 'A & B', 'about');
    expect(out).toContain('<g data-motif="" transform="translate(100 200) scale(1.5)">');
    expect(out).toContain('<title>A &amp; B</title><desc>about</desc>');
  });

  it('cuts a crop of 16:9 at its canvas size', () => {
    const out = svgFile(src, { aspect: '16:10', native: false, t: 0 }, 't', 'd');
    expect(out).toMatch(/viewBox="0 0 1728 1080" width="1728" height="1080"/);
  });
});

describe('rasterFile', () => {
  it('sizes the root to the output pixels and slices to fill', () => {
    const src = { template: v.svg, rows, seeds: seeds('fireproof') };
    const out = rasterFile(src, NATIVE, 3840, 2160);
    expect(out).toMatch(/width="3840" height="2160"/);
    expect(out).toContain('preserveAspectRatio="xMidYMid slice"');
  });
});

describe('regimeTemplate', () => {
  it('picks by the regime of the seeds', () => {
    const plate = { dark: 'd', light: 'l' };
    expect(regimeTemplate(plate, seeds('fireproof'))).toBe('d');
    expect(regimeTemplate(plate, seeds('flexoki-light'))).toBe('l');
  });
});

describe('aboutLine', () => {
  it('names the variant, license and theme', () => {
    expect(aboutLine('walldye.com/x', 'default', 'CC0-1.0', 'fireproof')).toBe(
      'walldye.com/x · CC0-1.0 · theme fireproof',
    );
    expect(aboutLine('walldye.com/x', 'wide', '', 'fireproof')).toBe(
      'walldye.com/x?v=wide · theme fireproof',
    );
  });
});
