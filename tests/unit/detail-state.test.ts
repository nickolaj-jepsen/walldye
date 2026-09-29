import { describe, expect, it } from 'vitest';
import {
  type DetailState,
  keptCrop,
  readAddress,
  shapeOf,
  sizeFor,
  writeAddress,
} from '../../src/client/detail/state';
import { focusPosition } from '../../src/client/export/shape';

const NATIVE = new Set(['16:9', '9:19.5']);
const state = (patch: Partial<DetailState> = {}): DetailState => ({
  variant: 'default',
  aspect: '16:9',
  crop: null,
  size: '2560x1440',
  ...patch,
});

describe('readAddress', () => {
  it('reads the version, shape and crop', () => {
    expect(readAddress(new URLSearchParams('v=late&shape=16x10&crop=0.25'))).toEqual({
      variant: 'late',
      aspect: '16:10',
      crop: 0.25,
    });
  });

  it('leaves out an unknown shape and a crop that is not a plain decimal in 0..1', () => {
    for (const crop of ['', '0x1', '0.9junk', '1.5', '-0.1', 'NaN']) {
      expect(readAddress(new URLSearchParams({ shape: '4x3', crop }))).toEqual({});
    }
    expect(readAddress(new URLSearchParams('crop=.5')).crop).toBe(0.5);
    expect(readAddress(new URLSearchParams('crop=1')).crop).toBe(1);
  });
});

describe('writeAddress', () => {
  const url = new URL('https://walldye.com/schotter?t=nord&crop=0.3');

  it('leaves every default out', () => {
    expect(writeAddress(url, state(), NATIVE).search).toBe('?t=nord');
  });

  it('writes a crop only once placed, and only on a cropped shape', () => {
    expect(writeAddress(url, state({ aspect: '16:10' }), NATIVE).search).toBe(
      '?t=nord&shape=16x10',
    );
    expect(writeAddress(url, state({ aspect: '16:10', crop: 0.12345 }), NATIVE).search).toBe(
      '?t=nord&shape=16x10&crop=0.123',
    );
    expect(writeAddress(url, state({ aspect: '9:19.5', crop: 0.5 }), NATIVE).search).toBe(
      '?t=nord&shape=9x19.5',
    );
    expect(writeAddress(url, state({ variant: 'late' }), NATIVE).search).toBe('?t=nord&v=late');
  });
});

describe('shapeOf', () => {
  it('centers an unplaced crop on the focus and keeps a placed one', () => {
    const focus = [0.2, 0.5] as const;
    expect(shapeOf(state({ aspect: '16:10' }), NATIVE, focus)).toEqual({
      aspect: '16:10',
      native: false,
      t: focusPosition('16:10', focus),
    });
    expect(shapeOf(state({ aspect: '16:10', crop: 0.9 }), NATIVE, focus).t).toBe(0.9);
    expect(shapeOf(state({ aspect: '9:19.5' }), NATIVE, focus).native).toBe(true);
  });
});

describe('keptCrop', () => {
  it('keeps a placed crop only between shapes cropping along the same axis', () => {
    const placed = state({ aspect: '16:10', crop: 0.7 });
    expect(keptCrop(placed, '10:16', NATIVE)).toBe(0.7);
    expect(keptCrop(placed, '21:9', NATIVE)).toBeNull();
    expect(keptCrop(placed, '9:19.5', NATIVE)).toBeNull();
    expect(keptCrop(state({ aspect: '9:19.5', crop: 0.7 }), '10:16', NATIVE)).toBeNull();
  });
});

describe('sizeFor', () => {
  const all = () => true;

  it('keeps a size the shape offers, else takes the default size', () => {
    expect(sizeFor('16:9', '3840x2160', all)).toBe('3840x2160');
    expect(sizeFor('16:9', 'screen', all)).toBe('screen');
    expect(sizeFor('16:10', '3840x2160', all)).toBe('2560x1600');
    expect(sizeFor('16:10', '', all)).toBe('2560x1600');
  });

  it('skips sizes the browser cannot draw', () => {
    expect(sizeFor('16:9', '5120x2880', (s) => s !== '5120x2880')).toBe('2560x1440');
    expect(sizeFor('16:9', '', (s) => s === '1920x1080')).toBe('1920x1080');
    expect(sizeFor('16:9', '', () => false)).toBe('1920x1080');
  });
});
