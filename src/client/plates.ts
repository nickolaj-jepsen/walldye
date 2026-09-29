/**
 * Recoloured plate images for the index and the detail page. Templates and slots.json are cached,
 * templates in an LRU of about TEMPLATE_BUDGET bytes. At most MAX_PLATES plates load and recolour at
 * once, the waiting plate nearest the viewport first, and a plate no longer wanted leaves the queue;
 * their fetches, and decodes of template URLs, share MAX_FETCHES slots in turn. A plate shows its
 * template recoloured for the given seeds as a blob: URL (the template's own URL when that changes
 * nothing), swapped in only once decoded.
 */
import { type Aspect, CANVAS } from '../lib/content';
import {
  type PreparedTemplate,
  pickTemplate,
  prepareTemplate,
  recolour,
  type Slots,
} from '../lib/recolour';
import { isFireproof, type Regime, regimeOf, type Seeds } from '../lib/theme';
import { readJson } from './dom';
import { retrying } from './retry';

export const MAX_FETCHES = 6;
/** Plates recolouring at once: each holds its template text, and SVG images decoded together make long tasks. */
export const MAX_PLATES = 6;
export const TEMPLATE_BUDGET = 8 * 1024 * 1024;

/** One version's plate data: slots.json key to template URL, the slots.json URL and the alt text. */
export interface PlateData {
  templates: Record<string, string>;
  slots: string;
  alt: string;
}

/** A place in a queue. */
interface Turn {
  /** The element whose distance from the viewport orders the waiters; without one, first come first served. */
  near?: Element;
  /** Whether the task is still wanted, asked while it waits; one no longer wanted rejects. */
  wanted?: () => boolean;
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

interface Waiter extends Turn {
  start: () => void;
  drop: () => void;
}

/** Pixels between `el` and the viewport, 0 when it is in view or there is no element. */
function offscreen(el: Element | undefined): number {
  if (!el) return 0;
  const r = el.getBoundingClientRect();
  return r.bottom < 0 ? -r.bottom : r.top > innerHeight ? r.top - innerHeight : 0;
}

class Queue {
  #active = 0;
  readonly #waiting = new Set<Waiter>();

  constructor(readonly limit: number) {}

  /**
   * Runs `task` once fewer than `limit` of this queue's tasks are running, the waiter nearest the
   * viewport first. Rejects without running `task` when it stops being wanted while it waits.
   */
  async run<T>(task: () => Promise<T>, turn: Turn = {}): Promise<T> {
    if (this.#active < this.limit) {
      this.#active++;
    } else {
      await new Promise<void>((resolve, reject) => {
        const drop = () => reject(new DOMException('no longer wanted', 'AbortError'));
        this.#waiting.add({ ...turn, start: resolve, drop });
      });
    }
    try {
      return await task();
    } finally {
      this.#release();
    }
  }

  #release(): void {
    let next: Waiter | undefined;
    let gap = Infinity;
    for (const w of this.#waiting) {
      if (w.wanted && !w.wanted()) {
        this.#waiting.delete(w);
        w.drop();
        continue;
      }
      const d = offscreen(w.near);
      if (d < gap) [next, gap] = [w, d];
    }
    // Hand the slot straight to the next waiter so a new caller cannot slip in between.
    if (next) {
      this.#waiting.delete(next);
      next.start();
    } else {
      this.#active--;
    }
  }
}

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

/** The template at `url`, split for recolouring; cached, least recently used evicted first. */
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

/** Gives the main thread a turn between recolours. */
function yieldToMain(): Promise<void> {
  const s = (globalThis as { scheduler?: { yield?: () => Promise<void> } }).scheduler;
  return s?.yield ? s.yield() : new Promise((resolve) => setTimeout(resolve, 0));
}

/**
 * `data`'s `aspect` template recoloured for `seeds`: the SVG text, the template URL and whether the
 * text is the template unchanged. Rejects when the slots or template cannot be loaded or the piece has
 * no template for `aspect`.
 */
export async function recoloured(
  data: PlateData,
  aspect: Aspect,
  seeds: Seeds,
): Promise<{ svg: string; url: string; untouched: boolean }> {
  const slots = await getSlots(data.slots);
  const picked = pickTemplate(slots, aspect, regimeOf(seeds));
  const url = data.templates[picked.key];
  if (!url) throw new Error(`no ${picked.key} template`);
  const tpl = await getTemplate(url);
  // A template whose URL does not carry its slots hash is not the one the coefficients were made for.
  if (!url.includes(`/${picked.entry.sha256.slice(0, 12)}.`)) {
    return { svg: tpl.svg, url, untouched: true };
  }
  await yieldToMain();
  const svg = recolour(tpl, picked.entry, seeds);
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
  const r = await recoloured(data, aspect, seeds);
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

/** Shows the untouched `aspect` template for `regime`, without slots.json: the stand-in while a recolour cannot be loaded. */
function showTemplate(plate: HTMLElement, data: PlateData, aspect: Aspect, regime: Regime): void {
  const url = data.templates[`${aspect}/${regime}`];
  if (url) show(plate, aspect, data.alt, async () => ({ url, blob: false })).catch(() => {});
}

/**
 * Shows `data`'s `aspect` template recoloured for `seeds` on `plate`, retrying failed loads
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
