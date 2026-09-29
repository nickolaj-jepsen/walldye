/**
 * The detail page: versions and their pictures, plate, crop window, export panel, run command, the
 * `f` key, "Copy" and the "See also" plates, shown in the page's shape.
 * A visitor's change goes through update(), which renders the whole page from the state and writes
 * the address; render() is cheap enough to run on every crop drag.
 */
import { type Aspect, DEFAULT_VARIANT, downloadName, FORMATS, isAspect } from '../../lib/content';
import { tokenOf } from '../../lib/theme';
import { copyText, flash } from '../clipboard';
import { must, readJson, replaceAddress } from '../dom';
import {
  canEncodeWebp,
  prefetchRasteriser,
  type RasterFormat,
  rasteriseSvg,
  save,
} from '../export/rasterise';
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
import { getSlots, keepShowing, type PlateData, plateData, recoloured } from '../plates';
import { retrying } from '../retry';
import { isPhone, screenPx } from '../screen';
import { currentSeeds, onThemeChange } from '../theme/current';
import { type DetailState, keptCrop, readAddress, shapeOf, sizeFor, writeAddress } from './state';

const plate = must('.spread .plate');
const cropWindow = must(':scope > .crop', plate);
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
const downloadKey = must('.k', downloadBtn);
const fileName = must('#download-name');
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
const phone = isPhone();
const screenAspect = nearestAspect(...screenPx());

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
  const aspect = asked.aspect ?? (phone && allowed('screen') ? screenAspect : '16:9');
  const keep = phone && aspect === screenAspect ? 'screen' : '';
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
  placeCrop(shape);
  renderSizes();
  renderNames(shape);
  renderPlate();
  seeAlso?.setShape(state.aspect);
}

function placeCrop(shape: ExportShape): void {
  cropWindow.hidden = shape.native;
  if (shape.native) return;
  const span = cropSpan(shape.aspect);
  const offset = shape.t * (1 - span);
  const axis = cropAxis(shape.aspect);
  cropWindow.dataset.axis = axis;
  // In % of the plate, so the frame also covers the plate's 0-7px rounding strip.
  Object.assign(
    cropWindow.style,
    axis === 'x'
      ? { left: `${offset * 100}%`, width: `${span * 100}%`, top: '0', height: '100%' }
      : { left: '0', width: '100%', top: `${offset * 100}%`, height: `${span * 100}%` },
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
  fileName.textContent = downloadName(
    slug,
    state.variant,
    token,
    f,
    `${w}x${h}`,
    state.aspect,
    !shape.native,
  );
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

cropWindow.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return;
  e.preventDefault();
  const x = cropAxis(state.aspect) === 'x';
  const travel = (x ? plate.clientWidth : plate.clientHeight) * (1 - cropSpan(state.aspect));
  const start = x ? e.clientX : e.clientY;
  const from = shapeOf(state, native, focus).t;
  cropWindow.setPointerCapture(e.pointerId);
  const move = (ev: PointerEvent) => {
    const d = (x ? ev.clientX : ev.clientY) - start;
    const next = Math.min(1, Math.max(0, from + (travel > 0 ? d / travel : 0)));
    update({ crop: Math.round(next * 1000) / 1000 });
  };
  const end = () => {
    cropWindow.removeEventListener('pointermove', move);
    cropWindow.removeEventListener('pointerup', end);
    cropWindow.removeEventListener('pointercancel', end);
  };
  cropWindow.addEventListener('pointermove', move);
  cropWindow.addEventListener('pointerup', end);
  cropWindow.addEventListener('pointercancel', end);
});

// ---- export ----

const piece = {
  title: document.querySelector('.label h1')?.textContent?.trim() ?? slug,
  licence: panel.dataset.license ?? '',
  // "walldye.com/<slug>" from the canonical URL, so previews and local builds name the real site.
  address: (() => {
    const href =
      document.querySelector<HTMLLinkElement>('link[rel=canonical]')?.href ?? location.href;
    const u = new URL(href);
    return `${u.host}${u.pathname}`;
  })(),
};

let busy = false;

async function runExport(): Promise<void> {
  if (busy) return;
  busy = true;
  downloadBtn.setAttribute('aria-busy', 'true');
  downloadKey.textContent = 'Preparing…';
  exportError.textContent = '';
  try {
    const f = format();
    const shape = shapeOf(state, native, focus);
    const seeds = currentSeeds();
    const data = dataOf(state.variant);
    const slots = await getSlots(data.slots);
    const r = await recoloured(data, sourceAspect(), seeds);
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
      const about = [address, piece.licence, `theme ${token}`].filter(Boolean).join(' · ');
      save(new Blob([svgExport(svg, shape, piece.title, about)], { type: 'image/svg+xml' }), name);
    } else {
      const raster = rasterSvg(svg, shape, w, h);
      save(await rasteriseSvg(raster.svg, seeds.bg, f.value as RasterFormat), name);
    }
  } catch {
    exportError.textContent = 'The file could not be made.';
  } finally {
    busy = false;
    downloadBtn.removeAttribute('aria-busy');
    downloadKey.textContent = 'Download';
  }
}

downloadBtn.addEventListener('click', () => void runExport());

const seen = new IntersectionObserver((entries) => {
  if (!entries.some((e) => e.isIntersecting)) return;
  seen.disconnect();
  prefetchRasteriser();
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
