/**
 * Main-thread side of the raster export: compiles resvg's wasm once (prefetched when the export panel
 * comes into view), runs each export in a fresh module Worker that is terminated afterwards, and
 * probes WebP support.
 */
import wasmUrl from '@resvg/resvg-wasm/index_bg.wasm?url';
import type { ExportRequest, ExportResponse } from './export-worker';

export type RasterFormat = ExportRequest['format'];

/** JPEG and WebP encoder quality. */
export const QUALITY = 0.92;

let wasm: Promise<WebAssembly.Module> | null = null;

async function compile(): Promise<WebAssembly.Module> {
  try {
    return await WebAssembly.compileStreaming(fetch(wasmUrl));
  } catch {
    // Served without application/wasm, or no streaming compile.
    return WebAssembly.compile(await (await fetch(wasmUrl)).arrayBuffer());
  }
}

function module(): Promise<WebAssembly.Module> {
  if (!wasm) {
    wasm = compile();
    wasm.catch(() => (wasm = null));
  }
  return wasm;
}

/** Starts downloading and compiling the rasteriser; failures surface on the next export instead. */
export function prefetchRasteriser(): void {
  module().catch(() => {});
}

let webp: Promise<boolean> | null = null;

/** Whether this browser can encode WebP, from a 1×1 encode (cached). */
export function canEncodeWebp(): Promise<boolean> {
  webp ??= (async () => {
    try {
      if (typeof OffscreenCanvas !== 'undefined') {
        const c = new OffscreenCanvas(1, 1);
        c.getContext('2d')?.fillRect(0, 0, 1, 1);
        return (await c.convertToBlob({ type: 'image/webp' })).type === 'image/webp';
      }
      const c = document.createElement('canvas');
      c.width = c.height = 1;
      return c.toDataURL('image/webp').startsWith('data:image/webp');
    } catch {
      return false;
    }
  })();
  return webp;
}

async function encodeOnPage(
  rgba: Uint8Array,
  width: number,
  height: number,
  format: RasterFormat,
): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('no 2d canvas');
  ctx.putImageData(
    new ImageData(
      new Uint8ClampedArray(rgba.buffer as ArrayBuffer, rgba.byteOffset, rgba.byteLength),
      width,
      height,
    ),
    0,
    0,
  );
  const type = `image/${format}`;
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, QUALITY));
  if (!blob || blob.type !== type) throw new Error(`no ${type} encoder`);
  return blob;
}

/**
 * `svg` (already sized to the output pixels) rasterised over `background` and encoded as `format`.
 * Rejects when rendering or encoding fails.
 */
export async function rasteriseSvg(
  svg: string,
  background: string,
  format: RasterFormat,
): Promise<Blob> {
  const compiled = await module();
  const worker = new Worker(new URL('./export-worker.ts', import.meta.url), { type: 'module' });
  try {
    const res = await new Promise<ExportResponse>((resolve, reject) => {
      worker.onmessage = (e: MessageEvent<ExportResponse>) => resolve(e.data);
      worker.onerror = (e) => reject(new Error(e.message || 'export worker failed'));
      const req: ExportRequest = { wasm: compiled, svg, background, format, quality: QUALITY };
      worker.postMessage(req);
    });
    if (!res.ok) throw new Error(res.error);
    if ('blob' in res) return res.blob;
    return await encodeOnPage(res.rgba, res.width, res.height, format);
  } finally {
    worker.terminate();
  }
}

export function save(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.hidden = true;
  document.body.append(a);
  a.click();
  a.remove();
  // Some engines read the URL after click() returns.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
