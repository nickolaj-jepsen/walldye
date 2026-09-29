import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { initWasm } from '@resvg/resvg-wasm';
import { decode } from 'fast-png';
import { beforeAll, describe, expect, it } from 'vitest';
import { encodePngRgb, rasterize, toRgb } from '../../src/client/export/resvg';
import { rasterSvg } from '../../src/client/export/shape';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(`${ROOT}${rel}`);
const MANIFEST = JSON.parse(read('tests/fixtures/manifest.json').toString()) as {
  resvg: { svg: string; png: string; width: number; height: number; background: string };
};

beforeAll(async () => {
  const wasm = createRequire(import.meta.url).resolve('@resvg/resvg-wasm/index_bg.wasm');
  await initWasm(readFileSync(wasm));
});

describe('rasterize', () => {
  it('matches the resvg-py reference render', () => {
    const ref = MANIFEST.resvg;
    const expected = decode(read(ref.png));
    // The export path: the template sized to the output pixels, over the seed background.
    const { svg } = rasterSvg(
      read(ref.svg).toString(),
      { aspect: '16:9', native: true, t: 0 },
      ref.width,
      ref.height,
    );
    const got = rasterize(svg, ref.background);
    expect([got.width, got.height]).toEqual([expected.width, expected.height]);
    const rgb = toRgb(got.pixels);
    const want = expected.data;
    expect(expected.channels).toBe(3);
    let worst = 0;
    let off = 0;
    for (let i = 0; i < rgb.length; i++) {
      const d = Math.abs(rgb[i] - want[i]);
      worst = Math.max(worst, d);
      if (d > 1) off++;
    }
    expect(worst).toBeLessThanOrEqual(2);
    expect(off).toBe(0);
  });

  it('encodes an RGB PNG of the exact size', () => {
    const svg =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 2" width="40" height="20"><rect width="2" height="2" fill="#FF0000"/></svg>';
    const png = decode(encodePngRgb(rasterize(svg, '#0000FF')));
    expect([png.width, png.height, png.channels, png.depth]).toEqual([40, 20, 3, 8]);
    expect([...png.data.slice(0, 3)]).toEqual([255, 0, 0]);
    expect([...png.data.slice(-3)]).toEqual([0, 0, 255]);
  });
});
