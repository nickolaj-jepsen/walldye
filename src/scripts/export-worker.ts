/**
 * Export worker: rasterises one prepared SVG with resvg-wasm and encodes it, then waits to be
 * terminated. PNG is encoded here as RGB; JPEG and WebP go through OffscreenCanvas, and where the
 * worker has none the RGBA pixels go back for the page to encode.
 */
import { initWasm } from '@resvg/resvg-wasm';
import { encodePngRgb, rasterise } from './raster';

export interface ExportRequest {
  /** resvg's compiled index_bg.wasm. */
  wasm: WebAssembly.Module;
  /** SVG sized to the output pixels (export-svg.ts rasterSvg). */
  svg: string;
  /** CSS colour drawn under the SVG. */
  background: string;
  format: 'png' | 'webp' | 'jpeg';
  /** Encoder quality for JPEG and WebP, 0..1. */
  quality: number;
}

export type ExportResponse =
  | { ok: true; blob: Blob }
  | { ok: true; rgba: Uint8Array; width: number; height: number }
  | { ok: false; error: string };

// The project compiles against the DOM lib, not the webworker one.
const scope = self as unknown as {
  onmessage: ((e: MessageEvent<ExportRequest>) => void) | null;
  postMessage(message: ExportResponse, transfer?: Transferable[]): void;
};

async function run(req: ExportRequest): Promise<ExportResponse> {
  await initWasm(req.wasm);
  const raster = rasterise(req.svg, req.background);
  if (req.format === 'png') return { ok: true, blob: new Blob([encodePngRgb(raster) as BlobPart], { type: 'image/png' }) };
  const type = `image/${req.format}`;
  if (typeof OffscreenCanvas === 'undefined') return { ok: true, rgba: raster.pixels, width: raster.width, height: raster.height };
  const canvas = new OffscreenCanvas(raster.width, raster.height);
  const ctx = canvas.getContext('2d');
  if (!ctx) return { ok: true, rgba: raster.pixels, width: raster.width, height: raster.height };
  const data = new Uint8ClampedArray(raster.pixels.buffer as ArrayBuffer, raster.pixels.byteOffset, raster.pixels.byteLength);
  ctx.putImageData(new ImageData(data, raster.width, raster.height), 0, 0);
  const blob = await canvas.convertToBlob({ type, quality: req.quality });
  // Engines without an encoder for `type` silently return PNG.
  if (blob.type !== type) return { ok: false, error: `no ${type} encoder` };
  return { ok: true, blob };
}

scope.onmessage = async (e: MessageEvent<ExportRequest>) => {
  let res: ExportResponse;
  try {
    res = await run(e.data);
  } catch (err) {
    res = { ok: false, error: String(err) };
  }
  if (res.ok && 'rgba' in res) scope.postMessage(res, [res.rgba.buffer]);
  else scope.postMessage(res);
};
