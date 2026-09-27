/**
 * Rasterising with resvg-wasm and PNG encoding, free of DOM and worker globals so the export worker
 * and the unit tests share it. initWasm() must have run once before rasterise().
 */
import { Resvg } from '@resvg/resvg-wasm';
import { encode } from 'fast-png';

export interface Raster {
  width: number;
  height: number;
  /** RGBA, straight alpha (opaque wherever the background covers). */
  pixels: Uint8Array;
}

/** `svg` drawn at its own width and height over `background` (a CSS colour). resvg's errors propagate. */
export function rasterise(svg: string, background: string): Raster {
  const resvg = new Resvg(svg, { background, fitTo: { mode: 'original' }, font: { loadSystemFonts: false } });
  try {
    const img = resvg.render();
    try {
      return { width: img.width, height: img.height, pixels: img.pixels };
    } finally {
      img.free();
    }
  } finally {
    resvg.free();
  }
}

/** RGBA pixels with the alpha channel dropped. */
export function toRgb(rgba: Uint8Array): Uint8Array {
  const out = new Uint8Array((rgba.length / 4) * 3);
  for (let i = 0, j = 0; i < rgba.length; i += 4, j += 3) {
    out[j] = rgba[i];
    out[j + 1] = rgba[i + 1];
    out[j + 2] = rgba[i + 2];
  }
  return out;
}

/** An 8-bit RGB PNG of `raster` (wallpapers are opaque; some wallpaper setters mishandle alpha). */
export function encodePngRgb(raster: Raster): Uint8Array {
  return encode({ width: raster.width, height: raster.height, data: toRgb(raster.pixels), channels: 3, depth: 8 });
}
