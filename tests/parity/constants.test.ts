import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { cropBox, focusPosition } from '../../src/client/export/shape';
import { CANVAS, SITE_ASPECTS } from '../../src/lib/content';
import {
  COLOR_WORDS,
  DEFAULT_LICENSE,
  FAN_WORK,
  MAX_VARIANTS,
  RESERVED_SLUGS,
} from '../../src/lib/meta';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string): unknown => JSON.parse(readFileSync(`${ROOT}${rel}`, 'utf8'));

interface Constants {
  site_aspects: string[];
  canvas: Record<string, [number, number]>;
  reserved_slugs: string[];
  color_words: string[];
  max_variants: number;
  default_license: string;
  fan_work: string;
}

interface Crop {
  aspect: string;
  focus: [number, number];
  t: number;
  box: [number, number, number, number];
}

describe('constants the Python tools also define', () => {
  const py = read('tests/fixtures/constants.json') as Constants;

  it('match', () => {
    expect([...SITE_ASPECTS]).toEqual(py.site_aspects);
    expect(CANVAS).toEqual(py.canvas);
    expect([...RESERVED_SLUGS].sort()).toEqual(py.reserved_slugs);
    expect([...COLOR_WORDS].sort()).toEqual(py.color_words);
    expect(MAX_VARIANTS).toBe(py.max_variants);
    expect(DEFAULT_LICENSE).toBe(py.default_license);
    expect(FAN_WORK).toBe(py.fan_work);
  });
});

describe('crops of the 16:9 canvas', () => {
  const crops = read('tests/fixtures/crops.json') as Crop[];

  it.each(crops)('$aspect around $focus', ({ aspect, focus, t, box }) => {
    expect(focusPosition(aspect, focus)).toBe(t);
    const b = cropBox(aspect, t);
    for (const [got, want] of [b.x, b.y, b.w, b.h].map((v, i) => [v, box[i]]))
      expect(got).toBeCloseTo(want, 9);
  });
});
