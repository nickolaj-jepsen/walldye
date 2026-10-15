import { describe, expect, it } from 'vitest';
import type { MotifInfo } from '../../lib/motif';
import { cropBox } from '../../lib/shape';
import {
  canvasRect,
  cropsInPlace,
  type DetailState,
  keptCrop,
  motifShift,
  parseAt,
  parseCrop,
  parseScale,
  placementOf,
  sizeFor,
  writeCrop,
  writeScale,
} from './state';

const MOON: MotifInfo = {
  at: [1305, 498],
  extent: [-279, -279, 558, 558],
  handle: [-279, -279, 558, 558],
  overscan: false,
  cell: 3,
  scale: [0.5, 2],
};
const START: DetailState = {
  variant: 'default',
  aspect: '16:9',
  crop: null,
  at: null,
  scale: null,
};

describe('the address', () => {
  it('reads whole-unit anchors and plain sizes only', () => {
    expect(parseAt('200,300')).toEqual([200, 300]);
    expect(parseScale('1.3333')).toBe(1.3333);
    for (const bad of ['-1,2', '1.5,2', '1,2,3', '']) expect(parseAt(bad)).toBeNull();
    for (const bad of ['0', '1e2', '1.23456', '']) expect(parseScale(bad)).toBeNull();
  });

  it('reads a crop only as a plain decimal in 0..1', () => {
    expect(parseCrop('0.25')).toBe(0.25);
    expect(parseCrop('.5')).toBe(0.5);
    for (const bad of ['0x1', '', '0.9junk', '1.5', '-0.1']) expect(parseCrop(bad)).toBeNull();
  });

  it('writes crops and sizes at their precision', () => {
    expect(writeCrop(0.12345)).toBe('0.123');
    expect(writeScale(1.5)).toBe('1.5');
  });
});

describe('placements', () => {
  it('leaves an untouched motif where it was drawn', () => {
    expect(placementOf(START, MOON)).toBeNull();
    expect(placementOf({ ...START, scale: 2 }, undefined)).toBeNull();
  });

  it('keeps the drawn anchor for a size alone, and clamps to the shape', () => {
    expect(placementOf({ ...START, scale: 1.1 }, MOON)).toEqual({ x: 1305, y: 498, k: 1 });
    expect(placementOf({ ...START, aspect: '9:19.5', at: [3000, 3000] }, MOON)).toEqual({
      x: 1080,
      y: 2340,
      k: 1,
    });
  });

  it('moves a drawn motif to another placement by one CSS transform', () => {
    // translate(to) scale(r) translate(-from) after translate(from) scale(from.k) is translate(to) scale(to.k).
    expect(motifShift({ x: 100, y: 50, k: 1 }, { x: 300, y: 80, k: 2 })).toBe(
      'translate(300px, 80px) scale(2) translate(-100px, -50px)',
    );
  });
});

describe('shapes', () => {
  const native = new Set(['16:9', '16:10']);

  it('keeps a placed crop only along the same axis', () => {
    const placed = { ...START, aspect: '9:19.5' as const, crop: 0.3 };
    expect(keptCrop(placed, '10:16', native)).toBe(0.3);
    expect(keptCrop(placed, '32:9', native)).toBeNull();
    expect(keptCrop(placed, '16:10', native)).toBeNull();
  });

  it('selects the kept size, else the default, else the first allowed', () => {
    const all = () => true;
    expect(sizeFor('16:9', 'screen', all)).toBe('screen');
    expect(sizeFor('16:9', '1920x1200', all)).toBe('2560x1440');
    expect(sizeFor('16:9', '', (s) => s === '1920x1080')).toBe('1920x1080');
  });

  it('crops in place only on narrow screens, for tall shapes cut from 16:9', () => {
    expect(cropsInPlace({ aspect: '9:19.5', native: false }, true)).toBe(true);
    expect(cropsInPlace({ aspect: '9:19.5', native: true }, true)).toBe(false);
    expect(cropsInPlace({ aspect: '21:9', native: false }, true)).toBe(false);
    expect(cropsInPlace({ aspect: '9:19.5', native: false }, false)).toBe(false);
  });
});

describe('the canvas under a plate', () => {
  it('fills a frame of its own ratio', () => {
    expect(canvasRect({ x: 0, y: 0, w: 1920, h: 1080 }, 1920, 1080, 16 / 9)).toEqual({
      left: '0%',
      top: '0%',
      width: '100%',
      height: '100%',
    });
  });

  it('centers a tall canvas in a 16:9 frame', () => {
    const r = canvasRect({ x: 0, y: 0, w: 1080, h: 2340 }, 1080, 2340, 16 / 9);
    expect(r.top).toBe('0%');
    expect(r.height).toBe('100%');
    expect(Number.parseFloat(r.left) * 2 + Number.parseFloat(r.width)).toBeCloseTo(100, 3);
  });

  it('runs past the frame where the frame shows a crop', () => {
    const view = cropBox('9:19.5', 1);
    const r = canvasRect(view, 1920, 1080, 1080 / 2340);
    // The crop sits at the right edge, so the canvas ends at the frame's right edge.
    expect(Number.parseFloat(r.left) + Number.parseFloat(r.width)).toBeCloseTo(100, 3);
    expect(r.height).toBe('100%');
  });
});
