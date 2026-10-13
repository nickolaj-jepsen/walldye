import { describe, expect, it } from 'vitest';
import {
  type DetailState,
  placementOf,
  readAddress,
  writeAddress,
} from '../../src/client/detail/state';
import type { MotifInfo } from '../../src/lib/motif';

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
  size: '2560x1440',
  at: null,
  scale: null,
};

describe('the motif in the address', () => {
  it('reads whole-unit anchors and plain sizes only', () => {
    expect(readAddress(new URLSearchParams('at=200,300&size=1.3333'))).toEqual({
      at: [200, 300],
      scale: 1.3333,
    });
    for (const bad of ['at=-1,2', 'at=1.5,2', 'at=1,2,3', 'size=0', 'size=1e2', 'size=1.23456']) {
      expect(readAddress(new URLSearchParams(bad))).toEqual({});
    }
  });

  it('writes what the visitor set and drops the rest', () => {
    const url = new URL('https://walldye.com/dither-moon?at=1,1&size=2');
    expect(writeAddress(url, START, new Set(['16:9'])).search).toBe('');
    const placed = { ...START, at: [200, 300] as [number, number], scale: 1.5 };
    expect(writeAddress(url, placed, new Set(['16:9'])).search).toBe('?at=200%2C300&size=1.5');
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
});
