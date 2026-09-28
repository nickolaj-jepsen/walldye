/**
 * Main-thread side of the in-browser drawing: one module Worker (draw-worker.ts), started on the
 * first request, which downloads and boots Pyodide once and then draws requests in order. A worker
 * that crashes fails its pending requests as `runtime` errors, and the next request starts a new one.
 */
import type { DrawProgress, DrawRequest, DrawResponse } from './draw-worker';

export type DrawJob = Omit<DrawRequest, 'id'>;
export type DrawResult = { svg: string; cells: number[]; ms: number };

/** A failed draw; `kind` as in DrawResponse. */
export class DrawError extends Error {
  constructor(
    readonly kind: 'design' | 'limit' | 'runtime',
    message: string,
  ) {
    super(message);
  }
}

let worker: Worker | null = null;
let nextId = 0;
/** Whether the worker has answered a draw, so Pyodide is loaded and the next draw needs no download. */
let booted = false;
const pending = new Map<number, { resolve: (r: DrawResult) => void; reject: (e: DrawError) => void }>();
const listeners = new Set<(fraction: number) => void>();

function fail(message: string): void {
  worker?.terminate();
  worker = null;
  booted = false;
  for (const p of pending.values()) p.reject(new DrawError('runtime', message));
  pending.clear();
}

function start(): Worker {
  const w = new Worker(new URL('./draw-worker.ts', import.meta.url), { type: 'module' });
  w.onmessage = (e: MessageEvent<DrawResponse | DrawProgress>) => {
    const msg = e.data;
    if ('progress' in msg) {
      for (const fn of listeners) fn(msg.progress);
      return;
    }
    const p = pending.get(msg.id);
    if (!p) return;
    pending.delete(msg.id);
    if (msg.ok) {
      booted = true;
      p.resolve({ svg: msg.svg, cells: msg.cells, ms: msg.ms });
    } else {
      booted ||= msg.kind !== 'runtime';
      p.reject(new DrawError(msg.kind, msg.error));
    }
  };
  w.onerror = (e) => fail(e.message || 'draw worker failed');
  return w;
}

/** Draws `job` in the worker; rejects with a DrawError. */
export function draw(job: DrawJob): Promise<DrawResult> {
  worker ??= start();
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    worker!.postMessage({ ...job, id } satisfies DrawRequest);
  });
}

/** Whether Pyodide is loaded, so a draw starts at once. */
export function isBooted(): boolean {
  return booted;
}

/** Calls `fn` with the share of Pyodide downloaded, 0 to 1, while it loads. */
export function onProgress(fn: (fraction: number) => void): void {
  listeners.add(fn);
}
