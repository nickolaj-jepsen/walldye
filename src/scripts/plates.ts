/**
 * Recoloured plate images for the index and the detail page. Templates and slots.json are fetched
 * at most MAX_FETCHES at a time and cached, templates in an LRU of about TEMPLATE_BUDGET bytes. A
 * plate shows its template recoloured for the given seeds as a blob: URL (the template's own URL
 * when that changes nothing), or a drawing made in the browser, swapped in only once decoded, after
 * which the previous blob: URL is revoked.
 */
import { pickTemplate, prepareTemplate, recolour, type PreparedTemplate, type Slots } from '../lib/recolour';
import { CANVAS, type Aspect } from '../lib/content';
import { normaliseSeeds, PRESETS, regimeOf, type Seeds } from '../lib/theme';

export const MAX_FETCHES = 6;
export const TEMPLATE_BUDGET = 8 * 1024 * 1024;
/** Waits before each retry of a plate whose template or slots failed to load; after the last, only the `online` event retries. */
export const RETRY_MS: readonly number[] = [1_000, 3_000, 10_000, 30_000];

let active = 0;
const waiting: (() => void)[] = [];

function acquire(): Promise<void> {
  if (active < MAX_FETCHES) {
    active++;
    return Promise.resolve();
  }
  return new Promise((resolve) => waiting.push(resolve));
}

function release(): void {
  // Hand the slot straight to the next waiter so a new caller cannot slip in between.
  const next = waiting.shift();
  if (next) next();
  else active--;
}

/** Runs `task` once fewer than MAX_FETCHES limited tasks are running. */
export async function limited<T>(task: () => Promise<T>): Promise<T> {
  await acquire();
  try {
    return await task();
  } finally {
    release();
  }
}

async function fetchText(url: string): Promise<string> {
  return limited(async () => {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    return res.text();
  });
}

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
export function getTemplate(url: string): Promise<PreparedTemplate> {
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

/** A plate's `data-templates`: slots.json key to template URL. */
export function templatesOf(plate: HTMLElement): Record<string, string> {
  try {
    return JSON.parse(plate.dataset.templates ?? '{}') as Record<string, string>;
  } catch {
    return {};
  }
}

function isFireproof(s: Seeds): boolean {
  const f = PRESETS.fireproof;
  return s.bg === f.bg && s.fg === f.fg && s.accent === f.accent;
}

/** Gives the main thread a turn between recolours. */
function yieldToMain(): Promise<void> {
  const s = (globalThis as { scheduler?: { yield?: () => Promise<void> } }).scheduler;
  return s?.yield ? s.yield() : new Promise((resolve) => setTimeout(resolve, 0));
}

interface Source {
  url: string;
  blob: boolean;
}

/**
 * `plate`'s `aspect` template recoloured for `seeds`: the SVG text, the template URL and whether the
 * text is the template unchanged. Rejects when the slots or template cannot be loaded or the piece has
 * no template for `aspect`.
 */
export async function recoloured(plate: HTMLElement, aspect: string, seeds: Seeds): Promise<{ svg: string; url: string; untouched: boolean }> {
  const s = normaliseSeeds(seeds);
  const urls = templatesOf(plate);
  const slots = await getSlots(plate.dataset.slots ?? '');
  const picked = pickTemplate(slots, aspect, regimeOf(s));
  const url = urls[picked.key];
  if (!url) throw new Error(`no ${picked.key} template`);
  const tpl = await getTemplate(url);
  // A template whose URL does not carry its slots hash is not the one the coefficients were made for.
  if (!url.includes(`/${picked.entry.sha256.slice(0, 12)}.`)) return { svg: tpl.svg, url, untouched: true };
  await yieldToMain();
  const svg = recolour(tpl, picked.entry, s);
  return { svg, url, untouched: svg === tpl.svg };
}

async function sourceFor(plate: HTMLElement, aspect: string, seeds: Seeds): Promise<Source> {
  const s = normaliseSeeds(seeds);
  if (isFireproof(s)) {
    const url = templatesOf(plate)[`${aspect}/dark`];
    if (url) return { url, blob: false };
  }
  const r = await recoloured(plate, aspect, s);
  if (r.untouched) return { url: r.url, blob: false };
  return { url: URL.createObjectURL(new Blob([r.svg], { type: 'image/svg+xml' })), blob: true };
}

const generation = new WeakMap<HTMLElement, number>();
const swapping = new WeakMap<HTMLElement, Promise<void>>();

function revoke(url: string | null): void {
  if (url?.startsWith('blob:')) URL.revokeObjectURL(url);
}

function fadeMs(img: HTMLElement): number {
  const d = getComputedStyle(img).transitionDuration.split(',')[0].trim();
  return d.endsWith('ms') ? parseFloat(d) : parseFloat(d) * 1000 || 0;
}

async function swapIn(plate: HTMLElement, src: Source, aspect: string, isCurrent: () => boolean): Promise<void> {
  const old = plate.querySelector<HTMLImageElement>(':scope > img');
  if (old?.getAttribute('src') === src.url) {
    if (src.blob) revoke(src.url);
    return;
  }
  const [w, h] = CANVAS[aspect as Aspect] ?? CANVAS['16:9'];
  const img = new Image(w, h);
  img.alt = plate.dataset.alt ?? '';
  img.decoding = 'async';
  img.dataset.aspect = aspect;
  img.src = src.url;
  try {
    if (src.blob) await img.decode();
    else await limited(() => img.decode());
  } catch {
    // Undecodable: show it anyway so the alt text stands in.
  }
  if (!isCurrent()) {
    if (src.blob) revoke(src.url);
    return;
  }
  img.style.opacity = '0';
  if (old) {
    img.style.position = 'absolute';
    img.style.top = '0';
    img.style.left = '0';
    old.after(img);
  } else {
    plate.insertBefore(img, plate.querySelector(':scope > .crop'));
  }
  const ms = fadeMs(img);
  // Read layout so the opacity change below transitions instead of applying at once.
  img.getBoundingClientRect();
  img.style.opacity = '';
  if (old) {
    if (ms > 0) await new Promise((resolve) => setTimeout(resolve, ms + 20));
    old.remove();
    img.style.removeProperty('position');
    img.style.removeProperty('top');
    img.style.removeProperty('left');
    revoke(old.getAttribute('src'));
  }
}

async function show(plate: HTMLElement, aspect: string, source: () => Promise<Source>): Promise<void> {
  const gen = (generation.get(plate) ?? 0) + 1;
  generation.set(plate, gen);
  const isCurrent = () => generation.get(plate) === gen;
  const src = await source();
  if (!isCurrent()) {
    if (src.blob) revoke(src.url);
    return;
  }
  const prev = swapping.get(plate) ?? Promise.resolve();
  const run = prev.then(() => (isCurrent() ? swapIn(plate, src, aspect, isCurrent) : src.blob ? revoke(src.url) : undefined));
  swapping.set(plate, run.catch(() => {}));
  await run;
}

/**
 * Shows `plate`'s `aspect` template for `seeds`. Later calls for the same plate (this or showTemplate)
 * supersede earlier ones; a superseded result is discarded. Rejects when the template or slots cannot be loaded.
 */
export function showPlate(plate: HTMLElement, aspect: string, seeds: Seeds): Promise<void> {
  return show(plate, aspect, () => sourceFor(plate, aspect, seeds));
}

/** Shows `svg`, a drawing of `plate` at `aspect`, as its image. Supersedes like showPlate. */
export function showSvg(plate: HTMLElement, aspect: string, svg: string): Promise<void> {
  return show(plate, aspect, async () => ({ url: URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' })), blob: true }));
}

/**
 * Shows `plate`'s untouched `aspect` template for the regime of `seeds`, without slots.json: the
 * stand-in while a recolour cannot be loaded. The image keeps the alt text even when the template itself
 * fails to load. Supersedes like showPlate.
 */
export async function showTemplate(plate: HTMLElement, aspect: string, seeds: Seeds): Promise<void> {
  const url = templatesOf(plate)[`${aspect}/${regimeOf(seeds)}`];
  if (url) await show(plate, aspect, async () => ({ url, blob: false }));
}
