/**
 * Draw worker: runs a design in Pyodide, loaded on the first request from the self-hosted
 * import.meta.env.PYODIDE_URL with the walldye library bundled from walldye/*.py, and answers each
 * request with the drawing serialised under a theme. While Pyodide loads it posts DrawProgress, the
 * share of the manifest's bytes fetched so far. Requests run one at a time, in order; the last few
 * documents are kept, so a new theme in the same regime only re-serialises.
 */
import type { PyodideInterface } from 'pyodide';

export interface DrawRequest {
  id: number;
  slug: string;
  /** design.py. */
  source: string;
  /** The piece's data/ files, fetched once per page. */
  data: { name: string; url: string }[];
  variant: string;
  /** Params that replace the version's, `seed` included. */
  params: Record<string, number | string | boolean | null>;
  aspect: string;
  regime: 'dark' | 'light';
  /** A theme token: a preset name or bg-fg-accent. */
  theme: string;
}

/**
 * The drawing and the milliseconds it took, or why there is none: `design` when the design raised
 * or refused the params, `limit` when the drawing breaks the template limits, `runtime` when
 * Pyodide itself failed.
 */
export type DrawResponse =
  | { id: number; ok: true; svg: string; cells: number[]; ms: number }
  | { id: number; ok: false; kind: 'design' | 'limit' | 'runtime'; error: string };

/** Loading progress, 0 to 1, posted while Pyodide downloads. */
export interface DrawProgress {
  progress: number;
}

// The project compiles against the DOM lib, not the webworker one.
const scope = self as unknown as {
  onmessage: ((e: MessageEvent<DrawRequest>) => void) | null;
  postMessage(message: DrawResponse | DrawProgress): void;
};

const LIBRARY = import.meta.glob<string>('/walldye/*.py', { query: '?raw', import: 'default', eager: true });
const HOME = '/home/pyodide';

// Kept in step with walldye/tools/common.py (load, draw) and lint.py (MAX_BYTES, MAX_ELEMENTS).
const GLUE = `
import dataclasses, importlib.util, json, sys
from walldye._design import RenderSpec
from walldye._theme import parse_theme

MAX_BYTES, MAX_ELEMENTS, KEEP = 1_000_000, 20_000, 4
_designs = {}
_docs = {}

def _design(slug, source):
    got = _designs.get(slug)
    if got is not None and got[0] == source:
        return got[1]
    name = "_walldye_" + slug.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, f"${HOME}/wallpapers/{slug}/design.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    _designs[slug] = (source, mod.draw)
    return mod.draw

def draw(slug, source, variant, params, aspect, regime, theme):
    d = _design(slug, source)
    key = (slug, source, variant, params, aspect, regime)
    doc = _docs.pop(key, None)
    if doc is None:
        p = dataclasses.replace(d.params(variant), **json.loads(params))
        doc = d.draw(RenderSpec(variant, p, aspect, regime))
    _docs[key] = doc
    while len(_docs) > KEEP:
        _docs.pop(next(iter(_docs)))
    svg = doc.to_svg(parse_theme(theme))
    big = len(svg.encode()) > MAX_BYTES or svg.count("\\n") > MAX_ELEMENTS
    return json.dumps({"svg": svg, "cells": sorted({c for c, _, _ in doc.pixel_grids}), "big": big})
`;

type Draw = (slug: string, source: string, variant: string, params: string, aspect: string, regime: string, theme: string) => string;

/** What the fetch wrapper counts: bytes from under `base` against `total`, while a boot runs. */
const counting = { base: '', total: 0, loaded: 0, posted: -1, installed: false };

/**
 * Starts counting the bodies of responses from under `base` against `total` bytes, posting
 * DrawProgress at every whole percent. Wraps fetch the first time.
 */
function countFetches(base: string, total: number): void {
  Object.assign(counting, { base, total, loaded: 0, posted: -1 });
  if (counting.installed) return;
  counting.installed = true;
  const g = globalThis as unknown as { fetch: typeof fetch };
  const real = g.fetch.bind(globalThis);
  g.fetch = async (input, init) => {
    const res = await real(input, init);
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (!res.body || counting.total <= 0 || !url.startsWith(counting.base)) return res;
    const counted = res.body.pipeThrough(
      new TransformStream<Uint8Array, Uint8Array>({
        transform(chunk, out) {
          counting.loaded += chunk.byteLength;
          const pct = Math.min(100, Math.floor((100 * counting.loaded) / counting.total));
          if (counting.total > 0 && pct > counting.posted) scope.postMessage({ progress: (counting.posted = pct) / 100 });
          out.enqueue(chunk);
        },
      }),
    );
    // Keep the headers: instantiateStreaming needs the wasm's application/wasm type.
    return new Response(counted, { status: res.status, statusText: res.statusText, headers: res.headers });
  };
}

let ready: Promise<{ py: PyodideInterface; draw: Draw }> | null = null;

async function boot(): Promise<{ py: PyodideInterface; draw: Draw }> {
  const base = new URL(import.meta.env.PYODIDE_URL, location.href).href;
  const res = await fetch(`${base}walldye.json`);
  if (!res.ok) throw new Error(`${base}walldye.json: HTTP ${res.status}`);
  const manifest = (await res.json()) as { packages: string[]; bytes: number };
  countFetches(base, manifest.bytes);
  const { loadPyodide } = (await import(/* @vite-ignore */ `${base}pyodide.mjs`)) as typeof import('pyodide');
  const py = await loadPyodide({ indexURL: base });
  await py.loadPackage(manifest.packages, { messageCallback: () => {} });
  counting.total = 0;
  scope.postMessage({ progress: 1 });
  py.FS.mkdirTree(`${HOME}/lib/walldye`);
  for (const [path, text] of Object.entries(LIBRARY)) py.FS.writeFile(`${HOME}/lib${path}`, text);
  py.runPython(`import sys; sys.path.insert(0, "${HOME}/lib")`);
  py.runPython(GLUE);
  return { py, draw: py.globals.get('draw') as Draw };
}

/** Slug to the design.py text last written for it. */
const written = new Map<string, string>();

async function install(py: PyodideInterface, req: DrawRequest): Promise<void> {
  if (written.get(req.slug) === req.source) return;
  const dir = `${HOME}/wallpapers/${req.slug}`;
  py.FS.mkdirTree(`${dir}/data`);
  for (const f of req.data) {
    const res = await fetch(f.url);
    if (!res.ok) throw new Error(`${f.url}: HTTP ${res.status}`);
    py.FS.writeFile(`${dir}/data/${f.name}`, new Uint8Array(await res.arrayBuffer()));
  }
  py.FS.writeFile(`${dir}/design.py`, req.source);
  written.set(req.slug, req.source);
}

async function handle(req: DrawRequest): Promise<DrawResponse> {
  let draw: Draw;
  try {
    ready ??= boot();
    const got = await ready;
    await install(got.py, req);
    draw = got.draw;
  } catch (e) {
    ready = null;
    return { id: req.id, ok: false, kind: 'runtime', error: String(e) };
  }
  try {
    const start = performance.now();
    const out = JSON.parse(draw(req.slug, req.source, req.variant, JSON.stringify(req.params), req.aspect, req.regime, req.theme)) as {
      svg: string;
      cells: number[];
      big: boolean;
    };
    if (out.big) return { id: req.id, ok: false, kind: 'limit', error: 'the drawing is over the template limits' };
    return { id: req.id, ok: true, svg: out.svg, cells: out.cells, ms: performance.now() - start };
  } catch (e) {
    return { id: req.id, ok: false, kind: 'design', error: String(e) };
  }
}

let queue: Promise<void> = Promise.resolve();

scope.onmessage = (e: MessageEvent<DrawRequest>) => {
  queue = queue.then(async () => scope.postMessage(await handle(e.data)));
};
