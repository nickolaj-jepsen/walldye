import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  allowedPlacement,
  centerMotif,
  clampPlacement,
  type MotifInfo,
  motifAlone,
  motifGround,
  motifSize,
  motifTransform,
  motifWindow,
  pinchMotif,
  placedBox,
  placeMotif,
  resizeMotif,
} from '../../src/lib/motif';

const SPEC = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../src/lib/__fixtures__/motif.json', import.meta.url)),
    'utf8',
  ),
) as {
  transform: { x: number; y: number; k: number; out: string }[];
  place: { svg: string; x: number; y: number; k: number; out: string }[];
  ground: { svg: string; out: string }[];
  alone: { svg: string; box: number[]; out: string }[];
  placements: {
    motif: MotifInfo;
    canvas: [number, number];
    place: [number, number, number];
    ok: boolean;
    clamped: [number, number, number];
  }[];
};

describe('the shared motif fixture', () => {
  it.each(SPEC.transform)('transform $x $y $k', ({ x, y, k, out }) => {
    expect(motifTransform({ x, y, k })).toBe(out);
  });
  it.each(SPEC.place)('place $x $y $k', ({ svg, x, y, k, out }) => {
    expect(placeMotif(svg, { x, y, k })).toBe(out);
  });
  it.each(SPEC.ground)('ground', ({ svg, out }) => {
    expect(motifGround(svg)).toBe(out);
  });
  it.each(SPEC.alone)('alone $box', ({ svg, box, out }) => {
    expect(motifAlone(svg, box)).toBe(out);
  });
  it.each(SPEC.placements)(
    'placement $place on $canvas',
    ({ motif, canvas, place, ok, clamped }) => {
      const [x, y, k] = place;
      expect(allowedPlacement(motif, ...canvas, { x, y, k })).toBe(ok);
      const c = clampPlacement(motif, ...canvas, { x, y, k });
      expect([c.x, c.y, c.k]).toEqual(clamped);
      expect(allowedPlacement(motif, ...canvas, c)).toBe(true);
    },
  );
});

const MOON: MotifInfo = {
  at: [1305, 498],
  extent: [-279, -279, 558, 558],
  handle: [-279, -279, 558, 558],
  overscan: false,
  cell: 3,
  scale: [0.5, 2],
};

describe('sizes', () => {
  it('keeps whole cells inside the scale', () => {
    const sizes = Array.from({ length: 31 }, (_, i) => motifSize(MOON, 0.4 + i * 0.06));
    expect(new Set(sizes)).toEqual(new Set([0.6667, 1, 1.3333, 1.6667, 2]));
  });
  it('falls back to the drawn size for a non-number', () => {
    expect(motifSize(MOON, Number.NaN)).toBe(1);
  });
});

describe('windows', () => {
  it('is the extent for a bounded motif', () => {
    expect(motifWindow(MOON, 1920, 1080, { x: 0, y: 0, k: 2 })).toEqual(MOON.extent);
  });
  it('is the grown canvas in motif units for an overscan one, kept to the extent', () => {
    const cover: MotifInfo = { ...MOON, overscan: true, extent: [-3840, -2160, 7680, 4320] };
    expect(motifWindow(cover, 1920, 1080, { x: 960, y: 540, k: 2 })).toEqual([
      -720, -405, 1440, 810,
    ]);
    expect(motifWindow(cover, 1920, 1080, { x: 0, y: 0, k: 0.5 })).toEqual([
      -960, -540, 4800, 2700,
    ]);
  });
  it('maps a local box onto the canvas', () => {
    expect(placedBox([-10, -20, 30, 40], { x: 100, y: 200, k: 2 })).toEqual([80, 160, 60, 80]);
  });
});

describe('centering', () => {
  const off: MotifInfo = { ...MOON, handle: [-40, -100, 200, 100], cell: null };
  it('puts the handle in the middle of one axis and keeps the other', () => {
    expect(centerMotif(off, 1920, 1080, { x: 10, y: 20, k: 1 }, 'x')).toEqual({
      x: 900,
      y: 20,
      k: 1,
    });
    expect(centerMotif(off, 1920, 1080, { x: 10, y: 20, k: 2 }, 'y')).toEqual({
      x: 10,
      y: 640,
      k: 2,
    });
  });
  it('keeps the anchor on the canvas', () => {
    expect(
      centerMotif({ ...off, handle: [-3000, 0, 10, 10] }, 1920, 1080, { x: 0, y: 0, k: 1 }, 'x').x,
    ).toBe(1920);
  });
});

describe('resizing by a corner', () => {
  const box: MotifInfo = { ...MOON, handle: [-100, -50, 200, 100], cell: null };
  const from = { x: 500, y: 300, k: 1 };
  it('keeps the opposite corner where it was', () => {
    // Bottom-right dragged out to double size: the top-left corner stays at (400, 250).
    expect(resizeMotif(box, 1920, 1080, from, [1, 1], [800, 450])).toEqual({
      x: 600,
      y: 350,
      k: 2,
    });
    // Top-left dragged in to half size: the bottom-right corner stays at (600, 350).
    expect(resizeMotif(box, 1920, 1080, from, [0, 0], [500, 300])).toEqual({
      x: 550,
      y: 325,
      k: 0.5,
    });
  });
  it('follows the pointer along the diagonal and keeps to the scale', () => {
    expect(resizeMotif(box, 1920, 1080, from, [1, 0], [700, 200]).k).toBe(1.5);
    expect(resizeMotif(box, 1920, 1080, from, [1, 1], [5000, 5000]).k).toBe(2);
    expect(resizeMotif(box, 1920, 1080, from, [1, 1], [0, 0]).k).toBe(0.5);
  });
});

describe('pinching', () => {
  const free: MotifInfo = { ...MOON, cell: null };
  const from = { x: 500, y: 300, k: 1 };
  it('scales by the fingers and keeps the point between them under them', () => {
    // Fingers 100 apart around (600, 300) spread to 200: the anchor 100 left of them goes to 200 left.
    expect(pinchMotif(free, 1920, 1080, from, [600, 300], 100, [600, 300], 200)).toEqual({
      x: 400,
      y: 300,
      k: 2,
    });
    // The same pinch carried 50 down.
    expect(pinchMotif(free, 1920, 1080, from, [600, 300], 100, [600, 350], 150)).toEqual({
      x: 450,
      y: 350,
      k: 1.5,
    });
  });
  it('keeps to the scale and moves with the fingers at its limit', () => {
    expect(pinchMotif(free, 1920, 1080, from, [600, 300], 100, [700, 300], 1000)).toEqual({
      x: 500,
      y: 300,
      k: 2,
    });
  });
});

describe('a large cell', () => {
  const big: MotifInfo = { ...MOON, cell: 32 };
  it('allows every size it offers', () => {
    for (let n = 16; n <= 64; n++) {
      expect(allowedPlacement(big, 1920, 1080, { x: 0, y: 0, k: motifSize(big, n / 32) })).toBe(
        true,
      );
    }
  });
});
