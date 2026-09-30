import { describe, expect, it } from 'vitest';
import { sameShape, slugOfPath } from '../../src/client/transition/move';

describe('slugOfPath', () => {
  it('reads a piece page', () => {
    expect(slugOfPath('/dither-moon')).toBe('dither-moon');
    expect(slugOfPath('/rule-30')).toBe('rule-30');
  });

  it('rejects the index, deeper paths and files', () => {
    for (const p of ['/', '', '/t/abc.svg', '/og/x.jpg', '/dither-moon/', '/Dither', '/-x'])
      expect(slugOfPath(p)).toBeNull();
  });
});

describe('sameShape', () => {
  it('matches a ratio with itself as serialized', () => {
    expect(sameShape(16 / 9, 1.77778)).toBe(true);
    expect(sameShape(9 / 19.5, 0.461538)).toBe(true);
  });

  it('tells shapes apart, even close ones', () => {
    expect(sameShape(16 / 9, 1.6)).toBe(false);
    expect(sameShape(16 / 9, 9 / 19.5)).toBe(false);
    expect(sameShape(0.625, 9 / 19.5)).toBe(false);
  });

  it('rejects ratios that could not be read', () => {
    expect(sameShape(Number.NaN, 16 / 9)).toBe(false);
    expect(sameShape(16 / 9, 0)).toBe(false);
  });
});
