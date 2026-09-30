/**
 * Recolored plate images for the index and the detail page. Templates and slots.json are cached,
 * templates in an LRU of about TEMPLATE_BUDGET bytes. At most MAX_PLATES plates load and recolor at
 * once, the waiting plate nearest the viewport first, and a plate no longer wanted leaves the queue;
 * their fetches, and decodes of template URLs, share MAX_FETCHES slots in turn. A plate shows its
 * template recolored for the given seeds as a blob: URL (the template's own URL when that changes
 * nothing), swapped in only once decoded.
 */
import { type Aspect, CANVAS } from '../lib/content';
import {
  type PreparedTemplate,
  pickTemplate,
  prepareTemplate,
  recolor,
  type Slots,
  templateUrl,
} from '../lib/recolor';
import { isFireproof, type Regime, regimeOf, type Seeds } from '../lib/theme';
import { readJson } from './dom';
import { Queue } from './queue';
import { retrying } from './retry';

export const MAX_FETCHES = 6;
/** Plates recoloring at once: each holds its template text, and SVG images decoded together make long tasks. */
export const MAX_PLATES = 6;
export const TEMPLATE_BUDGET = 8 * 1024 * 1024;

/**
 * One version's plate data: slots.json key to template URL, the slots.json URL and the alt text. A
 * key left out of `templates` is served where templateUrl() says, read from slots.json.
 */
export interface PlateData {
  templates: Record<string, string>;
  slots: string;
  alt: string;
}

/** The default version's data a server-rendered `.plate` carries. */
export function plateData(plate: HTMLElement): PlateData {
  return {
    templates: readJson(plate, 'templates', {}),
    slots: plate.dataset.slots ?? '',
    alt: plate.dataset.alt ?? '',
  };
}

// ---- the queues ----

const fetches = new Queue(MAX_FETCHES);
const plates = new Queue(MAX_PLATES);

function fetchText(url: string): Promise<string> {
  return fetches.run(async () => {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    return res.text();
  });
}

// ---- caches ----

const templates = new Map<string, PreparedTemplate>();
let templateBytes = 0;
const loading = new Map<string, Promise<PreparedTemplate>>();

function remember(url: string, t: PreparedTemplate): void {
  templates.set(url, t);
  templateBytes += t.svg.length;
  for (const [key, old] of templates) {
    if (templateBytes <= TEMPLATE_BUDGET || key === url) break;
    templates.delete(key);
    templateBytes -= old.svg.length;
  }
}

/** The template at `url`, split for recoloring; cached, least recently used evicted first. */
function getTemplate(url: string): Promise<PreparedTemplate> {
  const hit = templates.get(url);
  if (hit) {
    templates.delete(url);
    templates.set(url, hit);
    return Promise.resolve(hit);
  }
  let p = loading.get(url);
  if (!p) {
    p = fetchText(url)
      .then((svg) => {
        const t = prepareTemplate(svg);
        remember(url, t);
        return t;
      })
      .finally(() => loading.delete(url));
    loading.set(url, p);
  }
  return p;
}

const slotsCache = new Map<string, Promise<Slots>>();

/** The parsed slots.json at `url`, fetched once per page (a failed fetch is retried next time). */
export function getSlots(url: string): Promise<Slots> {
  let p = slotsCache.get(url);
  if (!p) {
    p = fetchText(url).then((text) => JSON.parse(text) as Slots);
    p.catch(() => slotsCache.delete(url));
    slotsCache.set(url, p);
  }
  return p;
}

/** Gives the main thread a turn between recolors. */
function yieldToMain(): Promise<void> {
  const s = (globalThis as { scheduler?: { yield?: () => Promise<void> } }).scheduler;
  return s?.yield ? s.yield() : new Promise((resolve) => setTimeout(resolve, 0));
}

/**
 * `data`'s `aspect` template recolored for `seeds`: the SVG text, the template URL and whether the
 * text is the template unchanged. Rejects when the slots or template cannot be loaded or the piece has
 * no template for `aspect`.
 */
export async function recolored(
  data: PlateData,
  aspect: Aspect,
  seeds: Seeds,
): Promise<{ svg: string; url: string; untouched: boolean }> {
  const slots = await getSlots(data.slots);
  const picked = pickTemplate(slots, aspect, regimeOf(seeds));
  const url = data.templates[picked.key] ?? templateUrl(picked.entry);
  const tpl = await getTemplate(url);
  // A template served under another hash is not the one the coefficients were made for.
  if (url !== templateUrl(picked.entry)) {
    return { svg: tpl.svg, url, untouched: true };
  }
  await yieldToMain();
  const svg = recolor(tpl, picked.entry, seeds);
  return { svg, url, untouched: svg === tpl.svg };
}

// ---- showing ----

interface Source {
  url: string;
  /** Whether `url` is a blob: URL this module made and must revoke. */
  blob: boolean;
}

function discard(src: Source): void {
  if (src.blob) URL.revokeObjectURL(src.url);
}

async function sourceFor(data: PlateData, aspect: Aspect, seeds: Seeds): Promise<Source> {
  if (isFireproof(seeds)) {
    const url = data.templates[`${aspect}/dark`];
    if (url) return { url, blob: false };
  }
  const r = await recolored(data, aspect, seeds);
  if (r.untouched) return { url: r.url, blob: false };
  return { url: URL.createObjectURL(new Blob([r.svg], { type: 'image/svg+xml' })), blob: true };
}

const generation = new WeakMap<HTMLElement, number>();
const swapping = new WeakMap<HTMLElement, Promise<void>>();

async function swapIn(
  plate: HTMLElement,
  src: Source,
  aspect: Aspect,
  alt: string,
  isCurrent: () => boolean,
): Promise<void> {
  const old = plate.querySelector<HTMLImageElement>(':scope > img');
  if (old?.getAttribute('src') === src.url) return discard(src);
  const [w, h] = CANVAS[aspect];
  const img = new Image(w, h);
  img.alt = alt;
  img.decoding = 'async';
  img.dataset.aspect = aspect;
  img.src = src.url;
  try {
    await (src.blob ? img.decode() : fetches.run(() => img.decode()));
  } catch {
    // Undecodable: show it anyway so the alt text stands in.
  }
  if (!isCurrent()) return discard(src);
  // site.css stacks it over `old` until the fade ends.
  img.style.opacity = '0';
  if (old) old.after(img);
  else plate.insertBefore(img, plate.querySelector(':scope > .crop'));
  // The frame site.css draws around a template that is not 16:9 takes this shape.
  plate.style.setProperty('--shape', String(w / h));
  // Read layout so the opacity change below transitions instead of applying at once.
  img.getBoundingClientRect();
  img.style.opacity = '';
  if (!old) return;
  // Waited out by the clock: animations in rows that content-visibility skips never finish.
  const endTimes = img.getAnimations().map((a) => Number(a.effect?.getComputedTiming().endTime));
  const fade = Math.max(0, ...endTimes.filter(Number.isFinite));
  if (fade > 0) await new Promise((resolve) => setTimeout(resolve, fade));
  old.remove();
  const oldSrc = old.getAttribute('src');
  if (oldSrc?.startsWith('blob:')) URL.revokeObjectURL(oldSrc);
}

/** Swaps in `source()`'s image; a later call for the same plate, or `signal` aborting, discards it. */
async function show(
  plate: HTMLElement,
  aspect: Aspect,
  alt: string,
  source: () => Promise<Source>,
  signal?: AbortSignal,
): Promise<void> {
  const gen = (generation.get(plate) ?? 0) + 1;
  generation.set(plate, gen);
  const isCurrent = () => generation.get(plate) === gen && !signal?.aborted;
  const src = await source();
  const prev = swapping.get(plate) ?? Promise.resolve();
  const run = prev.then(() =>
    isCurrent() ? swapIn(plate, src, aspect, alt, isCurrent) : discard(src),
  );
  swapping.set(
    plate,
    run.catch(() => {}),
  );
  await run;
}

/** Shows the untouched `aspect` template for `regime`, without slots.json: the stand-in while a recolor cannot be loaded. */
function showTemplate(plate: HTMLElement, data: PlateData, aspect: Aspect, regime: Regime): void {
  const url = data.templates[`${aspect}/${regime}`];
  if (url) show(plate, aspect, data.alt, async () => ({ url, blob: false })).catch(() => {});
}

/**
 * Shows `data`'s `aspect` template recolored for `seeds` on `plate`, retrying failed loads
 * (retrying()); meanwhile an empty plate gets the untouched template, so its alt text stands in.
 * `shown` runs once the image is in; `wanted` false drops it from the queue while it waits. Returns a
 * function that stops it, after which it swaps nothing in.
 */
export function keepShowing(
  plate: HTMLElement,
  data: PlateData,
  aspect: Aspect,
  seeds: Seeds,
  { shown, wanted }: { shown?: () => void; wanted?: () => boolean } = {},
): () => void {
  const ctrl = new AbortController();
  const turn = { near: plate, wanted: () => !ctrl.signal.aborted && (wanted?.() ?? true) };
  const draw = () => sourceFor(data, aspect, seeds);
  const stop = retrying(
    () => plates.run(() => show(plate, aspect, data.alt, draw, ctrl.signal), turn),
    {
      done: shown,
      failed: () => {
        if (!plate.querySelector(':scope > img'))
          showTemplate(plate, data, aspect, regimeOf(seeds));
      },
    },
  );
  return () => {
    stop();
    ctrl.abort();
  };
}

/**
 * A slot for one showing that restarts only when its key changes: `show(key, start)` stops the
 * running showing and calls `start` for a new one, and does nothing when `key` is the last one's.
 */
export function keyedShow(): (key: string, start: () => () => void) => void {
  let shown: string | undefined;
  let stop = () => {};
  return (key, start) => {
    if (key === shown) return;
    shown = key;
    stop();
    stop = start();
  };
}
