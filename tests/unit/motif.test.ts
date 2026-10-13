import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  allowedPlacement,
  clampPlacement,
  type MotifInfo,
  motifAlone,
  motifGround,
  motifSize,
  motifTransform,
  motifWindow,
  placedBox,
  placeMotif,
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

const MOON: MotifInfo = SPEC.placements[0].motif;

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
