import { describe, expect, it } from 'vitest';
import {
  cellWidths,
  crispPixels,
  cropAxis,
  cropBox,
  exportScale,
  fitRect,
  focusPosition,
  nearestAspect,
  num,
  rasterSvg,
  renderCommand,
  setRoot,
  svgExport,
  withinLimits,
  withTitle,
} from '../../src/scripts/export-svg';

const ROOT =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080" width="1920" height="1080">';

describe('crop geometry', () => {
  it('moves narrower shapes along x and wider ones along y', () => {
    expect(cropAxis('16:10')).toBe('x');
    expect(cropAxis('9:19.5')).toBe('x');
    expect(cropAxis('21:9')).toBe('y');
    expect(cropAxis('32:9')).toBe('y');
  });

  it('spans the full height or width and clamps the position', () => {
    expect(cropBox('16:10', 0)).toEqual({ x: 0, y: 0, w: 1728, h: 1080 });
    expect(cropBox('16:10', 1)).toEqual({ x: 192, y: 0, w: 1728, h: 1080 });
    expect(cropBox('16:10', 7)).toEqual(cropBox('16:10', 1));
    expect(cropBox('32:9', 0.5)).toEqual({ x: 0, y: 270, w: 1920, h: 540 });
    expect(cropBox('10:16', Number.NaN).x).toBeCloseTo((1920 - 675) / 2);
  });

  it('centres the default crop on the focus, clamped to the canvas', () => {
    // schotter's focus x 0.4633; the 16:10 box spans 0.9 of the width.
    expect(focusPosition('16:10', [0.4633, 0.4788])).toBe(0.133);
    expect(focusPosition('16:10', [0.99, 0.5])).toBe(1);
    expect(focusPosition('16:10', [0.01, 0.5])).toBe(0);
    const t = focusPosition('21:9', [0.5, 0.4788]);
    const box = cropBox('21:9', t);
    expect((box.y + box.h / 2) / 1080).toBeCloseTo(0.4788, 2);
  });
});

describe('fitRect / exportScale', () => {
  it('takes the largest centred box of the ratio', () => {
    expect(fitRect({ x: 0, y: 0, w: 1920, h: 1080 }, 16 / 9)).toEqual({
      x: 0,
      y: 0,
      w: 1920,
      h: 1080,
    });
    expect(fitRect({ x: 0, y: 0, w: 1920, h: 1080 }, 1)).toEqual({
      x: 420,
      y: 0,
      w: 1080,
      h: 1080,
    });
    const r = fitRect(cropBox('21:9', 0), 3440 / 1440);
    expect(r.w).toBe(1920);
    expect(r.h).toBeCloseTo(803.72, 2);
  });

  it('gives pixels per canvas unit', () => {
    expect(exportScale({ aspect: '16:9', native: true, t: 0 }, 2560, 1440)).toBeCloseTo(4 / 3);
    expect(exportScale({ aspect: '9:19.5', native: true, t: 0 }, 1170, 2532)).toBeCloseTo(
      1170 / 1080,
    );
  });
});

describe('SVG rewriting', () => {
  it('sets the root size, viewBox and preserveAspectRatio', () => {
    const svg = `${ROOT}<rect/></svg>`;
    const out = setRoot(svg, { x: 1.23456, y: 0, w: 10, h: 5 }, 2560, 1280, 'xMidYMid slice');
    expect(out).toBe(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="1.2346 0 10 5" width="2560" height="1280" preserveAspectRatio="xMidYMid slice"><rect/></svg>',
    );
    expect(setRoot('<svg><g/></svg>', { x: 0, y: 0, w: 1, h: 1 }, 1, 1)).toBe(
      '<svg viewBox="0 0 1 1" width="1" height="1"><g/></svg>',
    );
    expect(setRoot('no svg', { x: 0, y: 0, w: 1, h: 1 }, 1, 1)).toBe('no svg');
  });

  it('marks only px paths as crisp', () => {
    const svg =
      '<path d="M0 0h1" class="px"/><path class="a px b" d="z"/><path d="z" class="pxx"/><path class="px" shape-rendering="auto"/><rect class="px"/>';
    expect(crispPixels(svg)).toBe(
      '<path shape-rendering="crispEdges" d="M0 0h1" class="px"/><path shape-rendering="crispEdges" class="a px b" d="z"/><path d="z" class="pxx"/><path class="px" shape-rendering="auto"/><rect class="px"/>',
    );
  });

  it('adds an escaped title and description', () => {
    expect(withTitle(`${ROOT}<g/></svg>`, 'A & B', 'x < y')).toBe(
      `${ROOT}<title>A &amp; B</title><desc>x &lt; y</desc><g/></svg>`,
    );
  });

  it('cuts SVG downloads to the crop at canvas size', () => {
    const out = svgExport(`${ROOT}</svg>`, { aspect: '16:10', native: false, t: 1 }, 'T', 'D');
    expect(out).toBe(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="192 0 1728 1080" width="1728" height="1080"><title>T</title><desc>D</desc></svg>',
    );
  });

  it('sizes raster input to the exact pixels', () => {
    const { svg, scale } = rasterSvg(
      `${ROOT}</svg>`,
      { aspect: '16:9', native: true, t: 0 },
      1920,
      1200,
    );
    expect(svg).toBe(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="96 0 1728 1080" width="1920" height="1200" preserveAspectRatio="xMidYMid slice"></svg>',
    );
    expect(scale).toBeCloseTo(1920 / 1728);
  });
});

describe('sizes', () => {
  it('maps a screen to the nearest aspect', () => {
    expect(nearestAspect(2560, 1440)).toBe('16:9');
    expect(nearestAspect(2880, 1800)).toBe('16:10');
    expect(nearestAspect(3440, 1440)).toBe('21:9');
    expect(nearestAspect(5120, 1440)).toBe('32:9');
    expect(nearestAspect(1170, 2532)).toBe('9:19.5');
    expect(nearestAspect(1200, 1920)).toBe('10:16');
  });

  it('refuses rasters over the browser limits', () => {
    expect(withinLimits(7680, 2160)).toBe(true);
    expect(withinLimits(4096, 4096)).toBe(true);
    expect(withinLimits(4097, 4096)).toBe(false);
    expect(withinLimits(32_768, 10)).toBe(false);
  });

  it('reports uneven cells only', () => {
    expect(cellWidths([], 1.5)).toBeNull();
    expect(cellWidths([3], 4 / 3)).toBeNull();
    expect(cellWidths([3], 1920 / 1728)).toEqual([3, 4]);
    expect(cellWidths([3, 6], 1.5)).toEqual([4, 9]);
  });

  it('formats numbers without trailing zeros', () => {
    expect(num(192)).toBe('192');
    expect(num(25.536)).toBe('25.536');
    expect(num(498.46153846)).toBe('498.4615');
    expect(num(0.1 + 0.2, 3)).toBe('0.3');
  });
});

describe('renderCommand', () => {
  it('names the aspect, the crop and the output like the SVG download', () => {
    expect(
      renderCommand('schotter', 'default', 'fireproof', { aspect: '16:9', native: true, t: 0 }),
    ).toBe('uv run walldye render schotter --theme fireproof -o schotter-fireproof-16x9.svg');
    expect(renderCommand('moon', 'default', 'nord', { aspect: '9:19.5', native: true, t: 0 })).toBe(
      'uv run walldye render moon --theme nord --aspect 9:19.5 -o moon-nord-9x19.5.svg',
    );
    expect(
      renderCommand('schotter', 'default', '0a0a0a-f0f0f0-ff0000', {
        aspect: '21:9',
        native: false,
        t: 0.5,
      }),
    ).toBe(
      'uv run walldye render schotter --theme 0a0a0a-f0f0f0-ff0000 --crop 0,128.571,1920,822.857 -o schotter-0a0a0a-f0f0f0-ff0000-21x9-crop.svg',
    );
  });

  it('names a named variant after the slug, in the flag and the output', () => {
    expect(
      renderCommand('radar-sweep', 'open-sea', 'nord', { aspect: '10:16', native: true, t: 0 }),
    ).toBe(
      'uv run walldye render radar-sweep --variant open-sea --theme nord --aspect 10:16 -o radar-sweep--open-sea-nord-10x16.svg',
    );
    expect(
      renderCommand('schotter', 'late', 'fireproof', { aspect: '21:9', native: false, t: 0.5 }),
    ).toBe(
      'uv run walldye render schotter --variant late --theme fireproof --crop 0,128.571,1920,822.857 -o schotter--late-fireproof-21x9-crop.svg',
    );
  });
});
