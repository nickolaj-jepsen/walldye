/**
 * The detail page: versions and their pictures, plate, crop window, export panel and the Download
 * under the attribution, run command, the `f` key, "Copy" and the "See also" plates, shown in the page's
 * shape. On narrow screens a tall cropped shape shows the crop in the plate itself, with the crop
 * window on a small 16:9 map in the export panel.
 * A visitor's change goes through update(), which renders the whole page from the state and writes
 * the address; render() is cheap enough to run on every crop drag.
 */
import {
  type Aspect,
  CANVAS,
  DEFAULT_VARIANT,
  downloadName,
  FORMATS,
  isAspect,
} from '../../lib/content';
import { tokenOf } from '../../lib/theme';
import { copyText, flash } from '../clipboard';
import { must, readJson, replaceAddress } from '../dom';
import {
  canEncodeWebp,
  prefetchRasterizer,
  type RasterFormat,
  rasterizeSvg,
  save,
} from '../export/rasterize';
import {
  cellWidths,
  crispPixels,
  cropAxis,
  cropSpan,
  type ExportShape,
  exportScale,
  nearestAspect,
  rasterSvg,
  renderCommand,
  svgExport,
  withinLimits,
} from '../export/shape';
import { plateGrid } from '../grid';
import { getSlots, keepShowing, type PlateData, plateData, recolored } from '../plates';
import { retrying } from '../retry';
import { exportAspect, screenPx } from '../screen';
import { currentSeeds, onThemeChange } from '../theme/current';
import { type DetailState, keptCrop, readAddress, shapeOf, sizeFor, writeAddress } from './state';

const spread = must('.spread');
const plate = must('.plate', spread);
const cropWindow = must(':scope > .crop', plate);
const cropMap = must('.crop-map');
const mapWindow = must(':scope > .crop', cropMap);
const panel = must('#export');
const range = must<HTMLInputElement>('#crop');
const cropRow = must('#crop-row');
const shapeHint = must('#shape-hint');
const sizes = [...must('#sizes').querySelectorAll('label')].map((label) => ({
  label,
  input: must<HTMLInputElement>('input', label),
}));
const sizeLimit = must('#size-limit');
const cellNote = must('#cell-note');
const formatHint = must('#format-hint');
const downloadBtn = must<HTMLButtonElement>('#download');
const quickBtn = must<HTMLButtonElement>('#quick-download');
const downloadBtns = [downloadBtn, quickBtn];
const summaryParts = (part: string) => downloadBtns.map((btn) => must(`[data-part=${part}]`, btn));
const summaryFormats = summaryParts('format');
const summarySizes = summaryParts('size');
const summaryYours = summaryParts('yours');
const exportError = must('#export-error');
const desc = must('#desc');
const aspectRadios = [...panel.querySelectorAll<HTMLInputElement>('input[name=asp]')];
const formatRadios = [...panel.querySelectorAll<HTMLInputElement>('input[name=fmt]')];
// Pieces with versions only.
const versionsEl = document.getElementById('versions');
const versionRadios = [...(versionsEl?.querySelectorAll<HTMLInputElement>('input[name=v]') ?? [])];
const thumbs = [...(versionsEl?.querySelectorAll<HTMLElement>('.thumb[data-version]') ?? [])];
// Pieces that share a facet with another only.
const related = document.querySelector<HTMLElement>('section.related');
// Pieces with a script only.
const runRender = document.getElementById('run-render');
const copySource = document.querySelector<HTMLElement>('[data-action=copy-source]');

const slug = plate.dataset.plate ?? '';
const native = new Set(
  aspectRadios.filter((r) => r.hasAttribute('data-native')).map((r) => r.value),
);
const screenAspect = nearestAspect(...screenPx());
// Keep in step with site.css's phone query.
const narrow = matchMedia('(max-width: 60rem)');

/** Whether the plate shows `shape`'s crop itself: narrow screens, tall shapes cropped from 16:9 (the page's CSS). */
function cropsInPlace(shape: ExportShape): boolean {
  const [w, h] = CANVAS[shape.aspect];
  return narrow.matches && !shape.native && w < h;
}

/** Output pixels of a size radio's value. */
function sizePx(size: string): [number, number] {
  if (size === 'screen') return screenPx();
  const [w, h] = size.split('x').map(Number);
  return [w, h];
}
const allowed = (size: string) => withinLimits(...sizePx(size));

const defaultData = plateData(plate);
/** Every version's plate data by name, the default included; {} for a piece without named variants. */
const versions = readJson<Record<string, PlateData>>(plate, 'variants', {});
const dataOf = (variant: string): PlateData => versions[variant] ?? defaultData;

function format(): (typeof FORMATS)[number] {
  const v = formatRadios.find((r) => r.checked)?.value;
  return FORMATS.find((f) => f.value === v) ?? FORMATS[1];
}

// ---- state ----

const state: DetailState = (() => {
  const asked = readAddress(new URLSearchParams(location.search));
  // An unknown version, or a draft one outside `astro dev`, is not in `versions`: the default stays.
  const variant =
    asked.variant && Object.hasOwn(versions, asked.variant) ? asked.variant : DEFAULT_VARIANT;
  // As the shape boot chose, so the plate keeps its size.
  const aspect = asked.aspect ?? exportAspect();
  const keep = aspect === screenAspect ? 'screen' : '';
  return { variant, aspect, crop: asked.crop ?? null, size: sizeFor(aspect, keep, allowed) };
})();
/** The shown version's crop focus and grid cell sizes, from its slots.json once loaded. */
let focus: [number, number] = [0.5, 0.5];
let cells: number[] = [];

/** The state after switching to shape `next`, selecting size `keep` when it can. */
function withAspect(next: Aspect, keep: string): Partial<DetailState> {
  return { aspect: next, crop: keptCrop(state, next, native), size: sizeFor(next, keep, allowed) };
}

/** Applies a visitor's change: the state, the page and the address. */
function update(patch: Partial<DetailState>): void {
  const variantChanged = patch.variant !== undefined && patch.variant !== state.variant;
  Object.assign(state, patch);
  if (variantChanged) loadSlots();
  render();
  replaceAddress(writeAddress(new URL(location.href), state, native));
}

// ---- rendering ----

function render(): void {
  const data = dataOf(state.variant);
  const shape = shapeOf(state, native, focus);
  for (const r of versionRadios) r.checked = r.value === state.variant;
  if (desc.textContent !== data.alt) desc.textContent = data.alt;
  for (const img of plate.querySelectorAll<HTMLImageElement>(':scope > img')) img.alt = data.alt;
  for (const r of aspectRadios) r.checked = r.value === state.aspect;
  shapeHint.hidden = shape.native;
  cropRow.hidden = shape.native;
  range.value = String(shape.t);
  spread.dataset.aspect = state.aspect;
  const t = `${shape.t * 100}%`;
  plate.style.setProperty('--pos', cropAxis(shape.aspect) === 'x' ? `${t} 0%` : `0% ${t}`);
  for (const win of [cropWindow, mapWindow]) placeCrop(win, shape);
  renderSizes();
  renderNames(shape);
  renderPlate();
  if (cropsInPlace(shape)) renderMap();
  seeAlso?.setShape(state.aspect);
}

/** Frames `shape`'s crop with `win`, a `.crop` inside a plate showing the 16:9 picture. */
function placeCrop(win: HTMLElement, shape: ExportShape): void {
  win.hidden = shape.native;
  if (shape.native) return;
  const span = cropSpan(shape.aspect);
  const offset = shape.t * (1 - span);
  const axis = cropAxis(shape.aspect);
  win.dataset.axis = axis;
  // Heights are fractions of the picture's (site.css .plate::after), not the plate's, which ends in a 0-7px rounding strip.
  const tall = (f: number) => `calc(${f} * 100cqw / var(--ratio))`;
  Object.assign(
    win.style,
    axis === 'x'
      ? { left: `${offset * 100}%`, width: `${span * 100}%`, top: '0', height: tall(1) }
      : { left: '0', width: '100%', top: tall(offset), height: tall(span) },
  );
}

/** Shows the current shape's sizes, disabling those past the canvas limits. */
function renderSizes(): void {
  let limited = false;
  for (const { label, input } of sizes) {
    const offered = input.value === 'screen' || label.dataset.aspect === state.aspect;
    const ok = allowed(input.value);
    label.hidden = !offered;
    input.disabled = !offered || !ok;
    input.checked = input.value === state.size;
    if (offered && !ok) {
      input.setAttribute('aria-describedby', 'size-limit');
      limited = true;
    } else {
      input.removeAttribute('aria-describedby');
    }
  }
  sizeLimit.hidden = !limited;
}

function renderNames(shape: ExportShape): void {
  const token = tokenOf(currentSeeds());
  const f = format();
  const [w, h] = sizePx(state.size);
  const name = downloadName(
    slug,
    state.variant,
    token,
    f,
    `${w}x${h}`,
    state.aspect,
    !shape.native,
  );
  for (const btn of downloadBtns) btn.title = name;
  for (const el of summaryFormats) el.textContent = f.label;
  // An SVG has a shape but no pixel size.
  for (const el of summarySizes) el.textContent = f.value === 'svg' ? state.aspect : `${w}×${h}`;
  for (const el of summaryYours) el.hidden = f.value === 'svg' || state.size !== 'screen';
  if (runRender) runRender.textContent = renderCommand(slug, state.variant, token, shape);
  const widths =
    f.value === 'svg' || !cells.length ? null : cellWidths(cells, exportScale(shape, w, h));
  cellNote.hidden = !widths;
  if (widths) {
    const join = widths[1] - widths[0] > 1 ? 'to' : 'or';
    cellNote.textContent = `At this size the squares come out ${widths[0]} ${join} ${widths[1]} pixels wide.`;
  }
}

/** The template aspect the plate and export read: the shape's own, else 16:9 to crop. */
function sourceAspect(): Aspect {
  return native.has(state.aspect) ? state.aspect : '16:9';
}

let plateKey = '';
let stopPlate = () => {};
function renderPlate(): void {
  const seeds = currentSeeds();
  const key = `${state.variant} ${sourceAspect()} ${tokenOf(seeds)}`;
  if (key === plateKey) return;
  plateKey = key;
  stopPlate();
  stopPlate = keepShowing(plate, dataOf(state.variant), sourceAspect(), seeds);
}

let thumbsKey = '';
let stopThumbs: (() => void)[] = [];
/** Each version's 16:9 picture in the current theme. */
function renderThumbs(): void {
  const seeds = currentSeeds();
  const key = tokenOf(seeds);
  if (key === thumbsKey) return;
  thumbsKey = key;
  for (const stop of stopThumbs) stop();
  stopThumbs = thumbs.map((t) =>
    keepShowing(t, dataOf(t.dataset.version ?? DEFAULT_VARIANT), '16:9', seeds),
  );
}

let mapKey = '';
let stopMap = () => {};
/** The crop map's 16:9 picture in the current version and theme. */
function renderMap(): void {
  const seeds = currentSeeds();
  const key = `${state.variant} ${tokenOf(seeds)}`;
  if (key === mapKey) return;
  mapKey = key;
  stopMap();
  stopMap = keepShowing(cropMap, dataOf(state.variant), '16:9', seeds);
}

let stopSlots = () => {};
/** Reads the shown version's focus and cells from its slots.json, retrying a failed fetch. */
function loadSlots(): void {
  stopSlots();
  const url = dataOf(state.variant).slots;
  stopSlots = retrying(() =>
    getSlots(url).then((slots) => {
      if (url !== dataOf(state.variant).slots) return;
      focus = Array.isArray(slots.focus)
        ? [Number(slots.focus[0]), Number(slots.focus[1])]
        : [0.5, 0.5];
      cells = Array.isArray(slots.cells) ? slots.cells.map(Number).filter((c) => c > 0) : [];
      render();
    }),
  );
}

const seeAlso = related ? plateGrid(related, state.aspect) : undefined;
render();
renderThumbs();
loadSlots();
onThemeChange(() => {
  render();
  renderThumbs();
});
narrow.addEventListener('change', render);

// ---- panel events ----

versionsEl?.addEventListener('change', (e) => {
  const input = e.target as HTMLInputElement;
  if (input.name === 'v' && Object.hasOwn(versions, input.value)) update({ variant: input.value });
});

panel.addEventListener('change', (e) => {
  const input = e.target as HTMLInputElement;
  if (input.name === 'asp' && isAspect(input.value)) {
    const keep = state.size === 'screen' && input.value === screenAspect ? 'screen' : '';
    update(withAspect(input.value, keep));
  } else if (input.name === 'size') {
    // Picking "your screen" switches to the screen's shape.
    const toScreen = input.value === 'screen' && state.aspect !== screenAspect;
    update(toScreen ? withAspect(screenAspect, 'screen') : { size: input.value });
  } else if (input.name === 'fmt') {
    render();
  }
});

range.addEventListener('input', () => update({ crop: Number(range.value) }));

/**
 * Moves the crop with the drag `e` starts on `el`: the position changes by 1 / `travel` per pixel
 * moved, along the crop's axis, against the pointer when `reverse`.
 */
function dragCrop(el: HTMLElement, e: PointerEvent, travel: number, reverse = false): void {
  const x = cropAxis(state.aspect) === 'x';
  const start = x ? e.clientX : e.clientY;
  const from = shapeOf(state, native, focus).t;
  el.setPointerCapture(e.pointerId);
  const move = (ev: PointerEvent) => {
    const d = ((x ? ev.clientX : ev.clientY) - start) * (reverse ? -1 : 1);
    const next = Math.min(1, Math.max(0, from + (travel > 0 ? d / travel : 0)));
    update({ crop: Math.round(next * 1000) / 1000 });
  };
  const end = () => {
    el.removeEventListener('pointermove', move);
    el.removeEventListener('pointerup', end);
    el.removeEventListener('pointercancel', end);
  };
  el.addEventListener('pointermove', move);
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
}

// The crop window, on the plate or the map, travels over the rest of the 16:9 picture.
for (const [win, box] of [
  [cropWindow, plate],
  [mapWindow, cropMap],
] as const) {
  win.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const x = cropAxis(state.aspect) === 'x';
    const picture = x ? box.clientWidth : (box.querySelector('img')?.clientHeight ?? 0);
    dragCrop(win, e, picture * (1 - cropSpan(state.aspect)));
  });
}

// A plate showing the crop itself moves the picture under it, so the crop runs against the drag.
plate.addEventListener('pointerdown', (e) => {
  const img = plate.querySelector<HTMLImageElement>(':scope > img[data-aspect="16:9"]');
  if (e.button !== 0 || !img || !cropsInPlace(shapeOf(state, native, focus))) return;
  e.preventDefault();
  dragCrop(plate, e, (img.clientHeight * 16) / 9 - img.clientWidth, true);
});

// ---- export ----

const piece = {
  title: document.querySelector('.label h1')?.textContent?.trim() ?? slug,
  license: panel.dataset.license ?? '',
  // "walldye.com/<slug>" from the canonical URL, so previews and local builds name the real site.
  address: (() => {
    const href =
      document.querySelector<HTMLLinkElement>('link[rel=canonical]')?.href ?? location.href;
    const u = new URL(href);
    return `${u.host}${u.pathname}`;
  })(),
};

let busy = false;

/** Sets both Download buttons' word and busy state. */
function preparing(on: boolean): void {
  for (const btn of downloadBtns) {
    if (on) btn.setAttribute('aria-busy', 'true');
    else btn.removeAttribute('aria-busy');
    must('.k', btn).textContent = on ? 'Preparing…' : 'Download';
  }
}

/** Makes and saves the file; a failure writes `#export-error` and, from `from` outside the panel, scrolls it into view. */
async function runExport(from: HTMLElement): Promise<void> {
  if (busy) return;
  busy = true;
  preparing(true);
  exportError.textContent = '';
  try {
    const f = format();
    const shape = shapeOf(state, native, focus);
    const seeds = currentSeeds();
    const data = dataOf(state.variant);
    const slots = await getSlots(data.slots);
    const r = await recolored(data, sourceAspect(), seeds);
    const svg = Array.isArray(slots.cells) && slots.cells.length ? crispPixels(r.svg) : r.svg;
    const token = tokenOf(seeds);
    const [w, h] = sizePx(state.size);
    const name = downloadName(
      slug,
      state.variant,
      token,
      f,
      `${w}x${h}`,
      state.aspect,
      !shape.native,
    );
    if (f.value === 'svg') {
      const address =
        state.variant === DEFAULT_VARIANT ? piece.address : `${piece.address}?v=${state.variant}`;
      const about = [address, piece.license, `theme ${token}`].filter(Boolean).join(' · ');
      save(new Blob([svgExport(svg, shape, piece.title, about)], { type: 'image/svg+xml' }), name);
    } else {
      const raster = rasterSvg(svg, shape, w, h);
      save(await rasterizeSvg(raster.svg, seeds.bg, f.value as RasterFormat), name);
    }
  } catch {
    exportError.textContent = 'The file could not be made.';
    if (!panel.contains(from)) exportError.scrollIntoView({ block: 'center' });
  } finally {
    busy = false;
    preparing(false);
  }
}

for (const btn of downloadBtns) btn.addEventListener('click', () => void runExport(btn));

const seen = new IntersectionObserver((entries) => {
  if (!entries.some((e) => e.isIntersecting)) return;
  seen.disconnect();
  prefetchRasterizer();
  canEncodeWebp().then((ok) => {
    const webp = formatRadios.find((r) => r.value === 'webp');
    if (!webp || ok) return;
    webp.disabled = true;
    webp.setAttribute('aria-describedby', 'format-hint');
    formatHint.hidden = false;
    if (webp.checked) {
      for (const r of formatRadios) r.checked = r.value === 'png';
      render();
    }
  });
});
seen.observe(panel);
seen.observe(quickBtn);

// ---- keys ----

function toggleFullscreen(): void {
  if (!document.fullscreenEnabled || typeof plate.requestFullscreen !== 'function') return;
  if (document.fullscreenElement) void document.exitFullscreen();
  else plate.requestFullscreen().catch(() => {});
}

document.addEventListener('keydown', (e) => {
  if (e.defaultPrevented || e.repeat || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  if (document.getElementById('picker')?.matches(':popover-open')) return;
  const target = e.target instanceof Element ? e.target : null;
  if (target?.closest('input, textarea, select, [role=slider], [role=region]')) return;
  if (target instanceof HTMLElement && target.isContentEditable) return;
  if (e.key === 'f' || e.key === 'F') toggleFullscreen();
});

// ---- source code ----

copySource?.addEventListener('click', async () => {
  const raw = document.getElementById('raw-source') as HTMLTemplateElement | null;
  if (raw && (await copyText(raw.content.textContent ?? ''))) flash(copySource, 'Copied');
});
