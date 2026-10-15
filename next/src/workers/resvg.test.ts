import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { initWasm } from '@resvg/resvg-wasm';
import { decode } from 'fast-png';
import { beforeAll, describe, expect, it } from 'vitest';
import { encodePngRgb, rasterize, toRgb } from './resvg';

beforeAll(async () => {
  const require = createRequire(import.meta.url);
  await initWasm(readFileSync(require.resolve('@resvg/resvg-wasm/index_bg.wasm')));
});

describe('rasterize', () => {
  it('draws at the root size over the background', () => {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="2"><rect width="2" height="2" fill="#ff0000"/></svg>';
    const r = rasterize(svg, '#00ff00');
    expect([r.width, r.height]).toEqual([4, 2]);
    expect([...r.pixels.slice(0, 4)]).toEqual([255, 0, 0, 255]);
    expect([...r.pixels.slice(12, 16)]).toEqual([0, 255, 0, 255]);
  });
});

describe('encodePngRgb', () => {
  it('writes an opaque 8-bit RGB PNG', () => {
    const pixels = new Uint8Array([1, 2, 3, 255, 4, 5, 6, 255]);
    const png = decode(encodePngRgb({ width: 2, height: 1, pixels }));
    expect(png.channels).toBe(3);
    expect([...png.data]).toEqual([...toRgb(pixels)]);
  });
});
