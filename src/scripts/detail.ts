/**
 * The detail page: the recoloured plate, the crop window for shapes the piece has no template for,
 * the export panel, the run command, the copy button for the source, and the unadvertised `f` key
 * for fullscreen. docs/design.md, Detail, Aspect ratios and Export; src/scripts/DOM.md.
 *
 * The page's own query string holds `shape` (e.g. `16x10`, left out for 16:9) and `crop` (the crop
 * position, 0..1).
 */
import { aspectLabel, DEFAULT_SIZE_INDEX, downloadName, EXPORT_SIZES, FORMATS, SITE_ASPECTS, type Aspect } from '../lib/content';
import { appliedSeeds } from '../lib/recolour';
import { regimeOf, tokenOf, type Seeds } from '../lib/theme';
import { copyText, flash } from './clipboard';
import { currentSeeds, onThemeChange } from './current-theme';
import { canEncodeWebp, prefetchRasteriser, rasteriseSvg, save, type RasterFormat } from './export';
import {
  cellWidths,
  cropAxis,
  cropSpan,
  crispPixels,
  exportScale,
  focusPosition,
  nearestAspect,
  num,
  rasterSvg,
  renderCommand,
  svgExport,
  withinLimits,
  type ExportShape,
} from './export-svg';
import { getSlots, recoloured, RETRY_MS, showPlate, showTemplate, swapsFor, syncDarkNotes } from './plates';

const plate = document.querySelector<HTMLElement>('.spread .plate');
const cropWindow = plate?.querySelector<HTMLElement>(':scope > .crop') ?? null;
const panel = document.getElementById('export');
const range = document.getElementById('crop') as HTMLInputElement | null;
const cropRow = document.getElementById('crop-row');
const shapeHint = document.getElementById('shape-hint');
const sizesEl = document.getElementById('sizes');
const sizeLimit = document.getElementById('size-limit');
const cellNote = document.getElementById('cell-note');
const formatHint = document.getElementById('format-hint');
const downloadBtn = document.getElementById('download') as HTMLButtonElement | null;
const downloadKey = downloadBtn?.querySelector<HTMLElement>('.k') ?? null;
const fileName = document.getElementById('download-name');
const exportError = document.getElementById('export-error');
const runRender = document.getElementById('run-render');

const slug = plate?.dataset.plate ?? '';
const params = new URLSearchParams(location.search);
const phone = matchMedia('(max-width: 60rem) and (pointer: coarse)').matches;

const aspectRadios = [...(panel?.querySelectorAll<HTMLInputElement>('input[name=asp]') ?? [])];
const formatRadios = [...(panel?.querySelectorAll<HTMLInputElement>('input[name=fmt]') ?? [])];
const isAspect = (a: string | null): a is Aspect => (SITE_ASPECTS as readonly string[]).includes(a ?? '');
const nativeOf = (a: string) => aspectRadios.some((r) => r.value === a && r.hasAttribute('data-native'));

/** Output pixels of "your screen": the screen at device resolution. */
function screenPx(): [number, number] {
  const dpr = devicePixelRatio || 1;
  return [Math.round(screen.width * dpr), Math.round(screen.height * dpr)];
}
const screenAspect = nearestAspect(...screenPx());

const slotsUrl = plate?.dataset.slots ?? '';
let focus: [number, number] = [0.5, 0.5];
let cells: number[] = [];

// ---- state ----

let aspect: Aspect = '16:9';
/** Crop position along the moving axis; NaN until known (the focus arrives with slots.json). */
let t = NaN;
let size = '';
let slotsLoaded = false;

function shape(): ExportShape {
  return { aspect, native: nativeOf(aspect), t: Number.isFinite(t) ? t : 0.5 };
}

function sourceAspect(): string {
  return nativeOf(aspect) ? aspect : '16:9';
}

function format(): (typeof FORMATS)[number] {
  const v = formatRadios.find((r) => r.checked)?.value;
  return FORMATS.find((f) => f.value === v) ?? FORMATS[1];
}

function sizePx(): [number, number] {
  if (size === 'screen') return screenPx();
  const [w, h] = size.split('x').map(Number);
  return [w, h];
}

/** The seeds the export is drawn with (bg and fg swapped for a dark-only piece under light seeds) and their token. */
function exportTheme(): { seeds: Seeds; token: string } {
  const seeds = appliedSeeds(currentSeeds(), plate ? swapsFor(plate, sourceAspect(), currentSeeds()) : false);
  return { seeds, token: tokenOf(seeds) };
}

// ---- rendering the panel ----

function sizeLabel(value: string): HTMLLabelElement {
  const label = document.createElement('label');
  const input = document.createElement('input');
  input.type = 'radio';
  input.name = 'size';
  input.value = value;
  const span = document.createElement('span');
  if (value === 'screen') span.textContent = 'your screen';
  else {
    const mono = document.createElement('span');
    mono.className = 'mono';
    mono.textContent = value.replace('x', '×');
    span.append(mono);
  }
  label.append(input, span);
  return label;
}

/** Re-renders the size choices for the current shape, keeping `keep` when it is offered and allowed. */
function renderSizes(keep: string): void {
  if (!sizesEl) return;
  const list = EXPORT_SIZES[aspect];
  const options = [...list, 'screen'];
  const allowed = (v: string) => (v === 'screen' ? withinLimits(...screenPx()) : withinLimits(...(v.split('x').map(Number) as [number, number])));
  const fallback = [list[DEFAULT_SIZE_INDEX], ...options].find(allowed) ?? list[0];
  size = options.includes(keep) && allowed(keep) ? keep : fallback;
  const labels = options.map(sizeLabel);
  for (const l of labels) {
    const input = l.querySelector('input')!;
    input.checked = input.value === size;
    if (!allowed(input.value)) {
      input.disabled = true;
      input.setAttribute('aria-describedby', 'size-limit');
    }
  }
  sizesEl.replaceChildren(...labels);
  if (sizeLimit) sizeLimit.hidden = options.every(allowed);
}

function placeCrop(): void {
  if (!cropWindow) return;
  const s = shape();
  cropWindow.hidden = s.native;
  if (s.native) return;
  const span = cropSpan(aspect);
  const offset = s.t * (1 - span);
  const axis = cropAxis(aspect);
  cropWindow.dataset.axis = axis;
  // In % of the plate, like the prototype: the frame also covers the plate's 0-7px rounding strip.
  if (axis === 'x') Object.assign(cropWindow.style, { left: `${offset * 100}%`, width: `${span * 100}%`, top: '0', height: '100%' });
  else Object.assign(cropWindow.style, { left: '0', width: '100%', top: `${offset * 100}%`, height: `${span * 100}%` });
}

function renderNames(): void {
  const { token } = exportTheme();
  const s = shape();
  const f = format();
  const [w, h] = sizePx();
  if (fileName) fileName.textContent = downloadName(slug, token, f, `${w}x${h}`, aspect, !s.native);
  if (runRender) runRender.textContent = renderCommand(slug, token, s);
  if (cellNote) {
    const widths = f.value === 'svg' || !cells.length ? null : cellWidths(cells, exportScale(s, w, h));
    cellNote.hidden = !widths;
    if (widths) cellNote.textContent = `At this size the squares come out ${widths[0]} ${widths[1] - widths[0] > 1 ? 'to' : 'or'} ${widths[1]} pixels wide.`;
  }
}

function renderShape(): void {
  const native = nativeOf(aspect);
  for (const r of aspectRadios) r.checked = r.value === aspect;
  if (shapeHint) shapeHint.hidden = native;
  if (cropRow) cropRow.hidden = native;
  if (range && Number.isFinite(t)) range.value = String(t);
  placeCrop();
  renderNames();
}

let shownKey = '';
let plateFailures = 0;
let plateRetry = 0;
/** Shows the plate for the current shape and theme; a failed load leaves the untouched template in an empty plate and is retried. */
function renderPlate(): void {
  if (!plate) return;
  const a = sourceAspect();
  const seeds = currentSeeds();
  const key = `${a} ${tokenOf(seeds)}`;
  if (key === shownKey) return;
  shownKey = key;
  clearTimeout(plateRetry);
  showPlate(plate, a, seeds).then(
    () => {
      if (shownKey === key) plateFailures = 0;
    },
    () => {
      if (shownKey !== key) return;
      shownKey = '';
      if (!plate.querySelector(':scope > img')) showTemplate(plate, a, seeds).catch(() => {});
      if (plateFailures < RETRY_MS.length) plateRetry = window.setTimeout(renderPlate, RETRY_MS[plateFailures++]);
    },
  );
}

function syncUrl(): void {
  const url = new URL(location.href);
  url.searchParams.delete('shape');
  url.searchParams.delete('crop');
  if (aspect !== '16:9') url.searchParams.set('shape', aspectLabel(aspect));
  if (!nativeOf(aspect) && Number.isFinite(t)) url.searchParams.set('crop', num(t, 3));
  if (url.href !== location.href) history.replaceState(history.state, '', url.href);
}

/** Switches the shape, keeping the crop position when the crop moves on the same axis. */
function setAspect(next: Aspect, keepSize: string): void {
  const sameAxis = !nativeOf(aspect) && !nativeOf(next) && cropAxis(aspect) === cropAxis(next);
  aspect = next;
  if (!nativeOf(next) && !sameAxis) t = slotsLoaded ? focusPosition(next, focus) : NaN;
  renderSizes(keepSize);
  renderShape();
  renderPlate();
}

// ---- initial state ----

{
  const wanted = params.get('shape')?.replace('x', ':') ?? null;
  // Only a plain decimal: Number() alone would take "0x1" and "", parseFloat "0.9junk".
  const rawCrop = params.get('crop') ?? '';
  const crop = /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(rawCrop) ? Number(rawCrop) : NaN;
  if (isAspect(wanted)) aspect = wanted;
  else if (phone && withinLimits(...screenPx())) aspect = screenAspect;
  if (Number.isFinite(crop) && crop >= 0 && crop <= 1) t = crop;
  const phoneScreen = phone && aspect === screenAspect;
  renderSizes(phoneScreen ? 'screen' : '');
  renderShape();
  renderPlate();
}

let slotsFailures = 0;
let slotsRetry = 0;
/** Reads the crop focus and cell sizes from slots.json, retrying a failed fetch. */
function loadSlots(): void {
  if (!slotsUrl || slotsLoaded) return;
  clearTimeout(slotsRetry);
  getSlots(slotsUrl).then(
    (slots) => {
      if (slotsLoaded) return;
      slotsLoaded = true;
      focus = Array.isArray(slots.focus) ? [Number(slots.focus[0]), Number(slots.focus[1])] : focus;
      cells = Array.isArray(slots.cells) ? slots.cells.map(Number).filter((c) => c > 0) : [];
      if (!Number.isFinite(t) && !nativeOf(aspect)) t = focusPosition(aspect, focus);
      renderShape();
    },
    () => {
      if (slotsFailures < RETRY_MS.length) slotsRetry = window.setTimeout(loadSlots, RETRY_MS[slotsFailures++]);
    },
  );
}
loadSlots();
addEventListener('online', () => {
  plateFailures = 0;
  slotsFailures = 0;
  renderPlate();
  loadSlots();
});

syncDarkNotes(regimeOf(currentSeeds()) === 'light');
onThemeChange((seeds) => {
  syncDarkNotes(regimeOf(seeds) === 'light');
  renderPlate();
  renderNames();
});

// ---- panel events ----

panel?.addEventListener('change', (e) => {
  const input = e.target as HTMLInputElement;
  if (input.name === 'asp' && isAspect(input.value)) {
    setAspect(input.value, size === 'screen' && input.value === screenAspect ? 'screen' : '');
    syncUrl();
  } else if (input.name === 'size') {
    if (input.value === 'screen' && aspect !== screenAspect) {
      setAspect(screenAspect, 'screen');
      syncUrl();
    } else {
      size = input.value;
      renderNames();
    }
  } else if (input.name === 'fmt') {
    renderNames();
  }
});

range?.addEventListener('input', () => {
  t = Number(range.value);
  placeCrop();
  renderNames();
  syncUrl();
});

cropWindow?.addEventListener('pointerdown', (e) => {
  if (!plate || !range || e.button !== 0) return;
  e.preventDefault();
  const x = cropAxis(aspect) === 'x';
  const travel = (x ? plate.clientWidth : plate.clientHeight) * (1 - cropSpan(aspect));
  const start = x ? e.clientX : e.clientY;
  const from0 = shape().t;
  cropWindow.setPointerCapture(e.pointerId);
  const move = (ev: PointerEvent) => {
    const d = (x ? ev.clientX : ev.clientY) - start;
    const next = Math.min(1, Math.max(0, from0 + (travel > 0 ? d / travel : 0)));
    range.value = String(Math.round(next * 1000) / 1000);
    range.dispatchEvent(new Event('input', { bubbles: true }));
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
  licence: panel?.dataset.license ?? '',
  // "walldye.com/<slug>" from the canonical URL, so previews and local builds name the real site.
  address: (() => {
    const href = document.querySelector<HTMLLinkElement>('link[rel=canonical]')?.href ?? location.href;
    const u = new URL(href);
    return `${u.host}${u.pathname}`;
  })(),
};

let busy = false;

async function runExport(): Promise<void> {
  if (!plate || busy) return;
  busy = true;
  downloadBtn?.setAttribute('aria-busy', 'true');
  if (downloadKey) downloadKey.textContent = 'Preparing…';
  if (exportError) exportError.textContent = '';
  try {
    const f = format();
    const s = shape();
    const seeds = currentSeeds();
    const slots = await getSlots(slotsUrl);
    const r = await recoloured(plate, sourceAspect(), seeds);
    const svg = Array.isArray(slots.cells) && slots.cells.length ? crispPixels(r.svg) : r.svg;
    const exportSeeds = appliedSeeds(seeds, r.swap);
    const token = tokenOf(exportSeeds);
    const [w, h] = sizePx();
    const name = downloadName(slug, token, f, `${w}x${h}`, aspect, !s.native);
    if (f.value === 'svg') {
      const desc = [piece.address, piece.licence, `theme ${token}`].filter(Boolean).join(' · ');
      save(new Blob([svgExport(svg, s, piece.title, desc)], { type: 'image/svg+xml' }), name);
    } else {
      const raster = rasterSvg(svg, s, w, h);
      save(await rasteriseSvg(raster.svg, exportSeeds.bg, f.value as RasterFormat), name);
    }
  } catch {
    if (exportError) exportError.textContent = 'The file could not be made.';
  } finally {
    busy = false;
    downloadBtn?.removeAttribute('aria-busy');
    if (downloadKey) downloadKey.textContent = 'Download';
  }
}

downloadBtn?.addEventListener('click', () => void runExport());

if (panel) {
  const seen = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    seen.disconnect();
    prefetchRasteriser();
    canEncodeWebp().then((ok) => {
      const webp = formatRadios.find((r) => r.value === 'webp');
      if (!webp || ok) return;
      webp.disabled = true;
      webp.setAttribute('aria-describedby', 'format-hint');
      if (formatHint) formatHint.hidden = false;
      if (webp.checked) {
        webp.checked = false;
        formatRadios.find((r) => r.value === 'png')!.checked = true;
        renderNames();
      }
    });
  });
  seen.observe(panel);
}

// ---- keys ----

function toggleFullscreen(): void {
  if (!plate || !document.fullscreenEnabled || typeof plate.requestFullscreen !== 'function') return;
  if (document.fullscreenElement) void document.exitFullscreen();
  else plate.requestFullscreen().catch(() => {});
}

document.addEventListener('keydown', (e) => {
  if (e.defaultPrevented || e.repeat || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  if (document.getElementById('picker')?.matches(':popover-open')) return;
  const target = e.target instanceof Element ? e.target : null;
  if (target?.closest('input, textarea, select, [role=slider], [role=region]') || (target instanceof HTMLElement && target.isContentEditable)) return;
  if (e.key === 'f' || e.key === 'F') toggleFullscreen();
});

// ---- source code ----

const copySource = document.querySelector<HTMLElement>('[data-action=copy-source]');
copySource?.addEventListener('click', async () => {
  const raw = document.getElementById('raw-source') as HTMLTemplateElement | null;
  if (raw && (await copyText(raw.content.textContent ?? ''))) flash(copySource, 'Copied');
});
