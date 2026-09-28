/**
 * The detail page. Its query string holds `v` (the version, left out for the default), `shape`
 * (e.g. `16x10`, left out for 16:9), `crop` (0..1), and the visitor's edits to the drawing: a value
 * per changed knob under the knob's name, and `draw` (the seed).
 */
import { aspectLabel, DEFAULT_SIZE_INDEX, DEFAULT_VARIANT, downloadName, EXPORT_SIZES, FORMATS, SITE_ASPECTS, type Aspect } from '../lib/content';
import {
  DRAW_TRIES,
  dragValue,
  editsFromQuery,
  editsQuery,
  editsSuffix,
  isEdited,
  isText,
  noEdits,
  overrides,
  pickDraw,
  readout,
  setItems,
  validText,
  type Edits,
  type Knob,
  type ParamValue,
} from '../lib/controls';
import { regimeOf, tokenOf } from '../lib/theme';
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
import { draw as drawLive, isBooted, onProgress, type DrawError, type DrawJob, type DrawResult } from './live';
import { getSlots, recoloured, RETRY_MS, showPlate, showSvg, showTemplate } from './plates';

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
const versionsEl = document.getElementById('versions');
const versionRadios = [...(versionsEl?.querySelectorAll<HTMLInputElement>('input[name=v]') ?? [])];
const desc = document.getElementById('desc');
const drawingEl = document.getElementById('drawing');
const knobInputs = [...(drawingEl?.querySelectorAll<HTMLInputElement>('input[data-knob]') ?? [])];
const redrawBtn = drawingEl?.querySelector<HTMLButtonElement>('[data-action=redraw]') ?? null;
const restoreBtn = drawingEl?.querySelector<HTMLButtonElement>('[data-action=restore]') ?? null;
const drawStatus = document.getElementById('draw-status');

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

/** A version's plate data from the plate's `data-variants`. */
interface VersionData {
  templates: Record<string, string>;
  slots: string;
  alt: string;
}

/** The plate's versions by name, the default included; {} for a piece without named variants. */
const versions: Record<string, VersionData> = (() => {
  try {
    return JSON.parse(plate?.dataset.variants ?? '{}') as Record<string, VersionData>;
  } catch {
    return {};
  }
})();

/** `#drawing`'s `data-drawing`: each version's params and whether a new draw changes it, the knobs shown, the data files. */
interface DrawingData {
  versions: Record<string, { params: Record<string, ParamValue>; redraw: boolean }>;
  knobs: Knob[];
  data: { name: string; url: string }[];
}

/** The Drawing section's data; null when the page has none. */
const drawing: DrawingData | null = (() => {
  try {
    return drawingEl?.dataset.drawing ? (JSON.parse(drawingEl.dataset.drawing) as DrawingData) : null;
  } catch {
    return null;
  }
})();
const source = (document.getElementById('raw-source') as HTMLTemplateElement | null)?.content.textContent ?? '';

let slotsUrl = plate?.dataset.slots ?? '';
let focus: [number, number] = [0.5, 0.5];
let cells: number[] = [];

// ---- state ----

let variant = DEFAULT_VARIANT;
let aspect: Aspect = '16:9';
/** Crop position along the moving axis; NaN until known (the focus arrives with slots.json). */
let t = NaN;
/** Whether the visitor placed the crop (range, drag or `?crop=`); otherwise it follows the version's focus. */
let cropPlaced = false;
let size = '';
/** The slots.json whose focus and cells are in use. */
let loadedSlots = '';
/** Whether the address has been written since the page loaded; it then follows every change. */
let urlWritten = false;
/** The visitor's changes to the version on show; while there are any, the plate shows a drawing made here. */
let edits: Edits = noEdits();
/** The edits of what the plate last showed, which a failed draw falls back to. */
let shownEdits: Edits = noEdits();
/** The drawing on the plate, by jobKey; null while it shows the template. */
let shown: { key: string; result: DrawResult } | null = null;
/** How many draw numbers "Draw another" has tried since it was pressed; 0 when it is not trying. */
let redrawTries = 0;

const versionParams = (): Record<string, ParamValue> => drawing?.versions[variant]?.params ?? {};
const versionRedraws = (): boolean => drawing?.versions[variant]?.redraw ?? false;
const knobsShown = (): Knob[] => drawing?.knobs ?? [];
const copyEdits = (e: Edits): Edits => ({ draw: e.draw, knobs: { ...e.knobs } });

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
  // In % of the plate, so the frame also covers the plate's 0-7px rounding strip.
  if (axis === 'x') Object.assign(cropWindow.style, { left: `${offset * 100}%`, width: `${span * 100}%`, top: '0', height: '100%' });
  else Object.assign(cropWindow.style, { left: '0', width: '100%', top: `${offset * 100}%`, height: `${span * 100}%` });
}

/** The cell sizes of the pixel paths on show: the drawing's while one is edited, else the version's. */
function cellsShown(): number[] {
  return isEdited(edits) && shown ? shown.result.cells : cells;
}

function renderNames(): void {
  const token = tokenOf(currentSeeds());
  const s = shape();
  const f = format();
  const [w, h] = sizePx();
  const suffix = editsSuffix(edits, knobsShown());
  if (fileName) fileName.textContent = downloadName(slug, variant, token, f, `${w}x${h}`, aspect, !s.native, suffix);
  if (runRender) runRender.textContent = renderCommand(slug, variant, token, s, setItems(edits, knobsShown()), suffix);
  if (cellNote) {
    const now = cellsShown();
    const widths = f.value === 'svg' || !now.length ? null : cellWidths(now, exportScale(s, w, h));
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
/**
 * Shows the plate for the current shape and theme: the version's template, or while the drawing is
 * edited, a drawing made here. A failed template load leaves the untouched template in an empty
 * plate and is retried.
 */
function renderPlate(): void {
  if (!plate) return;
  if (isEdited(edits)) {
    shownKey = '';
    drawPlate();
    return;
  }
  shown = null;
  shownEdits = noEdits();
  wanted = null;
  setBusy(null);
  const a = sourceAspect();
  const seeds = currentSeeds();
  const key = `${variant} ${a} ${tokenOf(seeds)}`;
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

// ---- drawing in the browser ----

/** The draw the current state needs; null while the plate shows the version's template. */
function liveJob(): DrawJob | null {
  if (!drawing || !isEdited(edits)) return null;
  const seeds = currentSeeds();
  return { slug, source, data: drawing.data, variant, params: overrides(edits), aspect: sourceAspect(), regime: regimeOf(seeds), theme: tokenOf(seeds) };
}

const jobKey = (j: DrawJob): string => JSON.stringify([j.variant, j.params, j.aspect, j.regime, j.theme]);

/**
 * The newest job not yet sent, and the key of the one the worker is drawing; only the newest waiting
 * job is ever sent. A `quiet` job follows a knob that is still moving: it shows no busy state and
 * reports no failure, since the draw on release does both.
 */
let wanted: { job: DrawJob; quiet: boolean } | null = null;
let drawingKey: string | null = null;
let statusTimer = 0;
/** Whether the next drawPlate() follows a knob that is still moving. */
let quietNext = false;
/** Milliseconds the last draw took in the worker; knobs redraw as they move while it is under LIVE_MS. */
let lastMs = Infinity;
const LIVE_MS = 1000;
/** How long a draw runs before the status line says so; the plate's bar waits as long (site.md §6.9). */
const STATUS_MS = 300;

/** Sets the Drawing section's status line; an error keeps the error colour. */
function setStatus(text: string, error = false): void {
  clearTimeout(statusTimer);
  if (!drawStatus) return;
  drawStatus.textContent = text;
  drawStatus.classList.toggle('err', error);
}

/**
 * Marks the plate as drawing: `load` while Pyodide downloads (the bar shows the share done), `draw`
 * while the design runs, null when done. Only a phase change touches the status line.
 */
function setBusy(phase: 'load' | 'draw' | null): void {
  if (!plate || (plate.dataset.busy ?? null) === phase) return;
  if (phase === null) {
    delete plate.dataset.busy;
    plate.removeAttribute('aria-busy');
    if (!drawStatus?.classList.contains('err')) setStatus('');
    return;
  }
  plate.dataset.busy = phase;
  plate.setAttribute('aria-busy', 'true');
  if (phase === 'load') setStatus('Getting ready to draw…');
  else {
    setStatus(drawStatus?.textContent ? 'Drawing…' : '');
    // A quick redraw (a new theme, a drawing still in memory) is done before this fires.
    statusTimer = window.setTimeout(() => setStatus('Drawing…'), STATUS_MS);
  }
}

onProgress((fraction) => {
  plate?.style.setProperty('--progress', String(fraction));
  if (fraction >= 1 && plate?.dataset.busy === 'load') setBusy('draw');
});

/** Whether knobs should redraw while they move: Pyodide is ready and the last draw was quick. */
const liveDraws = (): boolean => isBooted() && lastMs < LIVE_MS;

/** Asks for the drawing the current state needs, unless the plate shows it already. */
function drawPlate(): void {
  const job = liveJob();
  const quiet = quietNext;
  quietNext = false;
  if (!job) return;
  wanted = shown?.key === jobKey(job) ? null : { job, quiet };
  void pump();
}

async function pump(): Promise<void> {
  if (drawingKey !== null || !wanted || !plate) return;
  const { job, quiet } = wanted;
  wanted = null;
  const key = jobKey(job);
  drawingKey = key;
  if (!quiet) setBusy(isBooted() ? 'draw' : 'load');
  const current = () => {
    const now = liveJob();
    return now !== null && jobKey(now) === key;
  };
  try {
    const result = await drawLive(job);
    lastMs = result.ms;
    if (current()) {
      shown = { key, result };
      shownEdits = copyEdits(edits);
      redrawTries = 0;
      // The new picture fades in over the last one as that brightens back.
      setBusy(null);
      await showSvg(plate, job.aspect, result.svg);
      renderNames();
    }
  } catch (e) {
    if (current() && !quiet) {
      setBusy(null);
      failed(e as DrawError);
    }
  } finally {
    drawingKey = null;
    // Nothing else to draw: the plate already shows the current state (drawPlate saw to that).
    if (!wanted) setBusy(null);
    void pump();
  }
}

/**
 * A draw of the current state failed. "Draw another" moves on to a new number, up to DRAW_TRIES in
 * all, when the design refused the number or broke the limits; anything else goes back to the
 * edits the plate shows, with an error.
 */
function failed(e: DrawError): void {
  if (redrawTries > 0 && redrawTries < DRAW_TRIES && e.kind !== 'runtime') {
    redrawTries++;
    edits.draw = pickDraw(edits.draw);
    afterEdit();
    return;
  }
  redrawTries = 0;
  // When the edits on show are what failed (a new theme or shape, or no Pyodide), the template stands in.
  const same = JSON.stringify(editsQuery(edits, knobsShown())) === JSON.stringify(editsQuery(shownEdits, knobsShown()));
  edits = same ? noEdits() : copyEdits(shownEdits);
  afterEdit();
  setStatus('This drawing could not be made.', true);
}

/** The value of every shown knob: the version's, with the edits over it. */
const knobValues = (): Record<string, ParamValue> => ({ ...versionParams(), ...edits.knobs });

/** Sets the input and readout of knob `k` to `v`; a text field being typed in keeps its text. */
function showKnob(k: Knob, v: ParamValue): void {
  for (const input of knobInputs) {
    if (input.dataset.knob !== k.name) continue;
    if (input.type === 'radio') input.checked = input.value === String(v);
    else if (input.type === 'checkbox') input.checked = v === true;
    else if (input.type !== 'text' || (document.activeElement !== input && input.value !== String(v))) {
      input.value = String(v);
      input.removeAttribute('aria-invalid');
    }
  }
  const out = drawingEl?.querySelector<HTMLElement>(`[data-readout="${k.name}"]`);
  if (out) out.textContent = readout(k, v) ?? '';
}

/** Sets every knob, readout and button of the Drawing section from the version and the edits. */
function renderEditState(): void {
  const values = knobValues();
  for (const k of knobsShown()) showKnob(k, values[k.name]);
  if (redrawBtn) redrawBtn.hidden = !versionRedraws();
  if (restoreBtn) restoreBtn.hidden = !isEdited(edits);
}

/** After the edits change: the controls, names, address and plate follow. */
function afterEdit(): void {
  renderEditState();
  renderNames();
  syncUrl();
  renderPlate();
}

/**
 * Sets each knob of `values`, dropping an edit that matches the version. With `settled` false (a
 * knob still moving) the address is left alone, since browsers limit how often it may be rewritten.
 */
function setKnobs(values: Record<string, ParamValue>, settled = true): void {
  redrawTries = 0;
  for (const [name, value] of Object.entries(values)) {
    if (value === versionParams()[name]) delete edits.knobs[name];
    else edits.knobs[name] = value;
  }
  if (drawStatus?.classList.contains('err')) setStatus('');
  if (settled) afterEdit();
  else {
    renderEditState();
    quietNext = true;
    renderPlate();
  }
}

/** The value an input of knob `k` holds. */
function inputValue(k: Knob, input: HTMLInputElement): ParamValue {
  if (k.choices) return k.choices.find((c) => String(c.value) === input.value)?.value ?? null;
  if (k.kind === 'bool') return input.checked;
  if (isText(k)) return input.value;
  return k.kind === 'int' ? Math.round(Number(input.value)) : Number(input.value);
}

function syncUrl(): void {
  urlWritten = true;
  const url = new URL(location.href);
  for (const key of ['v', 'shape', 'crop', 'draw', ...knobsShown().map((k) => k.name)]) url.searchParams.delete(key);
  if (variant !== DEFAULT_VARIANT) url.searchParams.set('v', variant);
  for (const [k, v] of editsQuery(edits, knobsShown())) url.searchParams.set(k, v);
  if (aspect !== '16:9') url.searchParams.set('shape', aspectLabel(aspect));
  if (!nativeOf(aspect) && Number.isFinite(t)) url.searchParams.set('crop', num(t, 3));
  if (url.href !== location.href) history.replaceState(history.state, '', url.href);
}

/** Switches the shape, keeping the crop position when the crop moves on the same axis. */
function setAspect(next: Aspect, keepSize: string): void {
  const sameAxis = !nativeOf(aspect) && !nativeOf(next) && cropAxis(aspect) === cropAxis(next);
  aspect = next;
  if (!nativeOf(next) && !sameAxis) {
    t = loadedSlots ? focusPosition(next, focus) : NaN;
    cropPlaced = false;
  }
  renderSizes(keepSize);
  renderShape();
  renderPlate();
}

/**
 * Makes `name` (a key of `versions`) the version on show: the plate's templates, slots and alt text,
 * the description and the radio. The caller renders; the focus and cells follow once its slots.json loads.
 */
function useVariant(name: string): void {
  const v = versions[name];
  if (!plate || !v) return;
  variant = name;
  plate.dataset.templates = JSON.stringify(v.templates);
  plate.dataset.slots = v.slots;
  plate.dataset.alt = v.alt;
  for (const img of plate.querySelectorAll<HTMLImageElement>(':scope > img')) img.alt = v.alt;
  if (desc) desc.textContent = v.alt;
  for (const r of versionRadios) r.checked = r.value === name;
  slotsUrl = v.slots;
}

// ---- initial state ----

{
  // An unknown version, or a draft one outside `astro dev`, is not in `versions`: the default stays.
  const v = params.get('v');
  if (v && Object.hasOwn(versions, v)) useVariant(v);
  if (drawing) {
    edits = editsFromQuery(params, drawing.knobs, versionParams(), versionRedraws());
    renderEditState();
  }
  const wantedShape = params.get('shape')?.replace('x', ':') ?? null;
  // Only a plain decimal: Number() alone would take "0x1" and "", parseFloat "0.9junk".
  const rawCrop = params.get('crop') ?? '';
  const crop = /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(rawCrop) ? Number(rawCrop) : NaN;
  if (isAspect(wantedShape)) aspect = wantedShape;
  else if (phone && withinLimits(...screenPx())) aspect = screenAspect;
  if (Number.isFinite(crop) && crop >= 0 && crop <= 1) {
    t = crop;
    cropPlaced = true;
  }
  const phoneScreen = phone && aspect === screenAspect;
  renderSizes(phoneScreen ? 'screen' : '');
  renderShape();
  renderPlate();
}

let slotsFailures = 0;
let slotsRetry = 0;
/**
 * Reads the crop focus and cell sizes from the version's slots.json, retrying a failed fetch. A crop
 * the visitor has not placed moves to the focus.
 */
function loadSlots(): void {
  const url = slotsUrl;
  if (!url || loadedSlots === url) return;
  clearTimeout(slotsRetry);
  getSlots(url).then(
    (slots) => {
      if (url !== slotsUrl || loadedSlots === url) return;
      loadedSlots = url;
      focus = Array.isArray(slots.focus) ? [Number(slots.focus[0]), Number(slots.focus[1])] : [0.5, 0.5];
      cells = Array.isArray(slots.cells) ? slots.cells.map(Number).filter((c) => c > 0) : [];
      if (!nativeOf(aspect) && !cropPlaced) t = focusPosition(aspect, focus);
      renderShape();
      if (urlWritten) syncUrl();
    },
    () => {
      if (url === slotsUrl && slotsFailures < RETRY_MS.length) slotsRetry = window.setTimeout(loadSlots, RETRY_MS[slotsFailures++]);
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

onThemeChange(() => {
  renderPlate();
  renderNames();
});

// ---- panel events ----

versionsEl?.addEventListener('change', (e) => {
  const input = e.target as HTMLInputElement;
  if (input.name !== 'v' || !Object.hasOwn(versions, input.value)) return;
  useVariant(input.value);
  edits = noEdits();
  redrawTries = 0;
  setStatus('');
  renderEditState();
  slotsFailures = 0;
  renderNames();
  renderPlate();
  loadSlots();
  syncUrl();
});

/** The shown knob an input of the Drawing section belongs to. */
const knobOf = (input: HTMLInputElement): Knob | undefined => knobsShown().find((k) => k.name === input.dataset.knob);

/** Waits after the last keystroke in a text knob before it draws. */
const TYPING_MS = 400;
let typingTimer = 0;

// A slider moves its readout as it goes and draws as it moves when draws are quick, else on
// release; text draws once typing pauses, and only when it is valid.
drawingEl?.addEventListener('input', (e) => {
  const input = e.target as HTMLInputElement;
  const k = knobOf(input);
  if (!k) return;
  if (input.type === 'range') {
    showKnob(k, inputValue(k, input));
    if (liveDraws()) setKnobs({ [k.name]: inputValue(k, input) }, false);
  } else if (isText(k)) {
    const ok = validText(k, input.value);
    input.setAttribute('aria-invalid', String(!ok));
    clearTimeout(typingTimer);
    if (ok) typingTimer = window.setTimeout(() => setKnobs({ [k.name]: input.value }), TYPING_MS);
  }
});

drawingEl?.addEventListener('change', (e) => {
  const input = e.target as HTMLInputElement;
  const k = knobOf(input);
  if (!k) return;
  if (isText(k)) {
    clearTimeout(typingTimer);
    // Leaving a field that holds no valid text puts back what is drawn.
    if (!validText(k, input.value)) input.value = String(knobValues()[k.name]);
    input.setAttribute('aria-invalid', 'false');
  }
  setKnobs({ [k.name]: inputValue(k, input) });
});

// ---- dragging the picture ----

/** The knobs that follow a drag across the plate. */
const dragKnobs = (): Knob[] => knobsShown().filter((k) => k.drag !== null);
if (plate && dragKnobs().length) {
  plate.dataset.drag = dragKnobs().map((k) => k.drag).join('');
  // A pressed image would start the browser's own drag, which cancels the pointer.
  plate.addEventListener('dragstart', (e) => e.preventDefault());
}

plate?.addEventListener('pointerdown', (e) => {
  const knobs = dragKnobs();
  if (!knobs.length || e.button !== 0 || (e.target as Element).closest('.crop')) return;
  // Vertical swipes scroll a touch screen (touch-action: pan-y), so a finger moves only the x knob.
  const moving = e.pointerType === 'touch' ? knobs.filter((k) => k.drag === 'x') : knobs;
  if (!moving.length) return;
  e.preventDefault();
  const box = plate.getBoundingClientRect();
  const from = Object.fromEntries(moving.map((k) => [k.name, Number(knobValues()[k.name])]));
  const values = (ev: PointerEvent) =>
    Object.fromEntries(
      moving.map((k) => {
        const share = k.drag === 'x' ? (ev.clientX - e.clientX) / box.width : (ev.clientY - e.clientY) / box.height;
        return [k.name, dragValue(k, from[k.name], share)];
      }),
    );
  plate.setPointerCapture(e.pointerId);
  plate.classList.add('dragging');
  const move = (ev: PointerEvent) => {
    const next = values(ev);
    if (liveDraws()) setKnobs(next, false);
    else for (const k of moving) showKnob(k, next[k.name]);
  };
  const end = (ev: PointerEvent) => {
    plate.classList.remove('dragging');
    plate.removeEventListener('pointermove', move);
    plate.removeEventListener('pointerup', end);
    plate.removeEventListener('pointercancel', end);
    // A cancelled drag (the page scrolled instead) puts the knobs back; its coordinates are not the pointer's.
    setKnobs(ev.type === 'pointercancel' ? from : values(ev));
  };
  plate.addEventListener('pointermove', move);
  plate.addEventListener('pointerup', end);
  plate.addEventListener('pointercancel', end);
});

redrawBtn?.addEventListener('click', () => {
  const seed = versionParams().seed;
  edits.draw = pickDraw(edits.draw ?? (typeof seed === 'number' ? seed : null));
  redrawTries = 1;
  setStatus('');
  afterEdit();
});

restoreBtn?.addEventListener('click', () => {
  edits = noEdits();
  redrawTries = 0;
  setStatus('');
  afterEdit();
  // The button hides itself; focus goes to the section's first control instead of the page.
  (redrawBtn && !redrawBtn.hidden ? redrawBtn : knobInputs[0])?.focus();
});

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
  cropPlaced = true;
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

/** "walldye.com/<slug>", with `?v=<variant>` for a named variant and the edits, if any. */
const address = () => {
  const query = new URLSearchParams([...(variant === DEFAULT_VARIANT ? [] : [['v', variant]]), ...editsQuery(edits, knobsShown())]).toString();
  return query ? `${piece.address}?${query}` : piece.address;
};

/** The SVG to export and its pixel cells: the edited drawing, else the version's template recoloured for `seeds`. */
async function exportSource(seeds: ReturnType<typeof currentSeeds>): Promise<{ svg: string; cells: number[] }> {
  const job = liveJob();
  if (job) return shown?.key === jobKey(job) ? shown.result : drawLive(job);
  const slots = await getSlots(slotsUrl);
  const r = await recoloured(plate!, sourceAspect(), seeds);
  return { svg: r.svg, cells: Array.isArray(slots.cells) ? slots.cells.map(Number) : [] };
}

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
    const src = await exportSource(seeds);
    const svg = src.cells.length ? crispPixels(src.svg) : src.svg;
    const token = tokenOf(seeds);
    const [w, h] = sizePx();
    const name = downloadName(slug, variant, token, f, `${w}x${h}`, aspect, !s.native, editsSuffix(edits, knobsShown()));
    if (f.value === 'svg') {
      const about = [address(), piece.licence, `theme ${token}`].filter(Boolean).join(' · ');
      save(new Blob([svgExport(svg, s, piece.title, about)], { type: 'image/svg+xml' }), name);
    } else {
      const raster = rasterSvg(svg, s, w, h);
      save(await rasteriseSvg(raster.svg, seeds.bg, f.value as RasterFormat), name);
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
