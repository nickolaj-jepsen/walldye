/**
 * The detail page: versions and their pictures, plate, crop window, motif placement, export panel and
 * the Download under the attribution, run command, the `f` key, "Copy" and the "See also" plates, shown
 * in the page's shape. On narrow screens a tall cropped shape shows the crop in the plate itself, with
 * the crop window on a small 16:9 map in the export panel.
 * A visitor's change goes through update(), which renders the whole page from the state and writes
 * the address; render() is cheap enough to run on every crop drag. A motif being moved shows on live
 * layers until the drag or range ends, when update() takes the placement and redraws the plate.
 */
import { type Aspect, CANVAS, DEFAULT_VARIANT, downloadName, isAspect } from '../../lib/content';
import {
  centerMotif,
  clampPlacement,
  drawnPlacement,
  type MotifInfo,
  motifTransform,
  type Placement,
  pinchMotif,
  placeMotif,
  resizeMotif,
} from '../../lib/motif';
import { pickTemplate, type Slots } from '../../lib/recolor';
import {
  cellWidths,
  cropAxis,
  cropSpan,
  type ExportShape,
  exportScale,
  nearestAspect,
  objectPosition,
  renderCommand,
} from '../../lib/shape';
import { regimeOf, type Seeds, tokenOf } from '../../lib/theme';
import { copyText, flash } from '../clipboard';
import { must, readJson, replaceAddress } from '../dom';
import { plateGrid } from '../grid';
import { getSlots, keepShowing, keyedShow, type PlateData, plateData, recolored } from '../plates';
import { retrying } from '../retry';
import { markShape, NARROW_QUERY, screenPx } from '../screen';
import { currentSeeds, onThemeChange } from '../theme/current';
import { dragCrop, placeCrop } from './crop';
import { setUpExport } from './export';
import { dragMotif, MotifView } from './motif';
import { allowed, formatOf, panelParts, renderPanel, sizePx, startState } from './panel';
import { type DetailState, keptCrop, placementOf, shapeOf, sizeFor, writeAddress } from './state';

const spread = must('.spread');
const plate = must('.plate', spread);
const cropWindow = must(':scope > .crop', plate);
const cropMap = must('.crop-map');
const mapWindow = must(':scope > .crop', cropMap);
const parts = panelParts();
const { panel, buttons: downloadBtns, formatRadios, native } = parts;
const range = must<HTMLInputElement>('#crop');
const cellNote = must('#cell-note');
const formatHint = must('#format-hint');
const exportError = must('#export-error');
const desc = must('#desc');
// Pieces with versions only.
const versionsEl = document.getElementById('versions');
const versionRadios = [...(versionsEl?.querySelectorAll<HTMLInputElement>('input[name=v]') ?? [])];
const thumbs = [...(versionsEl?.querySelectorAll<HTMLElement>('.thumb[data-version]') ?? [])];
// Pieces that share a facet with another only.
const related = document.querySelector<HTMLElement>('section.related');
// Pieces with a motif only.
const motifFrame = plate.querySelector<HTMLElement>(':scope > .motif-frame');
const motif = motifFrame ? new MotifView(motifFrame) : undefined;
const placeX = document.querySelector<HTMLInputElement>('#place-x');
const placeY = document.querySelector<HTMLInputElement>('#place-y');
const placeK = document.querySelector<HTMLInputElement>('#place-k');
const placeReset = document.getElementById('place-reset');
const placeCenter = {
  x: document.getElementById('place-cx'),
  y: document.getElementById('place-cy'),
};
// Pieces with a script only.
const runRender = document.getElementById('run-render');
const copySource = document.querySelector<HTMLElement>('[data-action=copy-source]');

const slug = plate.dataset.plate ?? '';
const screenAspect = nearestAspect(...screenPx());
const narrow = matchMedia(NARROW_QUERY);

/** Whether the plate shows `shape`'s crop itself: narrow screens, tall shapes cropped from 16:9 (the page's CSS). */
function cropsInPlace(shape: ExportShape): boolean {
  const [w, h] = CANVAS[shape.aspect];
  return narrow.matches && !shape.native && w < h;
}

const defaultData = plateData(plate);
/** Every version's plate data and description by name, the default included; {} for a piece without named variants. */
const versions = readJson<Record<string, PlateData & { description: string }>>(
  plate,
  'variants',
  {},
);
const dataOf = (variant: string): PlateData => versions[variant] ?? defaultData;

// ---- state ----

// As the boots chose, so the plate and the panel keep what they show.
const state: DetailState = startState(Object.keys(versions));
/** The shown version's crop focus, grid cell sizes and slots.json, once loaded. */
let focus: [number, number] = [0.5, 0.5];
let cells: number[] = [];
let slots: Slots | undefined;
let slotsUrl = '';
/** The placement a drag or range shows on the live layers before update() takes it. */
let preview: Placement | null = null;

/** The state after switching to shape `next`, selecting size `keep` when it can; the motif goes back to that shape's own place. */
function withAspect(next: Aspect, keep: string): Partial<DetailState> {
  return {
    aspect: next,
    crop: keptCrop(state, next, native),
    size: sizeFor(next, keep, allowed),
    at: null,
  };
}

/** The motif of the `source` template `loaded` lists for `seeds`, if any. */
function motifIn(loaded: Slots | undefined, source: Aspect, seeds: Seeds): MotifInfo | undefined {
  if (!loaded) return undefined;
  try {
    return pickTemplate(loaded, source, regimeOf(seeds)).entry.motif;
  } catch {
    return undefined;
  }
}

/** The motif of the template the plate shows, once the shown version's slots.json is loaded. */
function motifInfo(): MotifInfo | undefined {
  return motifIn(slots, sourceAspect(), currentSeeds());
}

/** Where the motif `info` shows now: the live preview, the visitor's placement or the design's. */
function shownPlacement(info: MotifInfo): Placement {
  return preview ?? placementOf(state, info) ?? drawnPlacement(info);
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
  const shape = shapeOf(state, native, focus, motifInfo());
  for (const r of versionRadios) r.checked = r.value === state.variant;
  const text = versions[state.variant]?.description;
  if (text !== undefined && desc.textContent !== text) desc.textContent = text;
  for (const img of plate.querySelectorAll<HTMLImageElement>(':scope > img')) img.alt = data.alt;
  range.value = String(shape.t);
  markShape(spread, 'aspect', state.aspect);
  plate.style.setProperty('--pos', objectPosition(shape.aspect, shape.t));
  for (const win of [cropWindow, mapWindow]) placeCrop(win, shape);
  renderPanel(parts, state);
  renderNames(shape);
  renderPlate();
  renderMotif();
  if (cropsInPlace(shape)) renderMap();
  seeAlso?.setShape(state.aspect);
}

function renderNames(shape: ExportShape): void {
  const token = tokenOf(currentSeeds());
  const f = formatOf(parts);
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
  if (runRender) runRender.textContent = renderCommand(slug, state.variant, token, shape);
  // The motif's cells grow with it.
  const cell = motifInfo()?.cell;
  const sized = cells.map((c) => (c === cell && shape.place ? c * shape.place.k : c));
  const widths =
    f.value === 'svg' || !sized.length ? null : cellWidths(sized, exportScale(shape, w, h));
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

const showPlate = keyedShow();
/** The plate's picture, its motif placed; the live layers go once it is in, or at once when it already shows. */
function renderPlate(): void {
  const seeds = currentSeeds();
  const place = placementOf(state, motifInfo());
  const key = `${state.variant} ${sourceAspect()} ${tokenOf(seeds)} ${place ? motifTransform(place) : ''}`;
  const started = showPlate(key, () =>
    keepShowing(plate, dataOf(state.variant), sourceAspect(), seeds, {
      edit: place ? (svg) => placeMotif(svg, place) : undefined,
      shown: () => {
        if (!preview) motif?.stop();
      },
    }),
  );
  if (!started && !preview) motif?.stop();
}

/** The motif's handle on the plate and its rows in the panel. */
function renderMotif(): void {
  const info = motifInfo();
  if (!motif || !placeX || !placeY || !placeK || !placeReset) return;
  const p = info ? shownPlacement(info) : { x: 0, y: 0, k: 1 };
  motif.place(info, sourceAspect(), p);
  if (!info) return;
  const [w, h] = CANVAS[state.aspect];
  const den = info.cell ?? 100;
  Object.assign(placeX, { max: String(w), value: String(Math.round(p.x)) });
  Object.assign(placeY, { max: String(h), value: String(Math.round(p.y)) });
  placeK.min = String(Math.ceil(info.scale[0] * den - 1e-9));
  placeK.max = String(Math.floor(info.scale[1] * den + 1e-9));
  placeK.value = String(Math.round(p.k * den));
  placeK.setAttribute('aria-valuetext', `${Math.round(p.k * 100)}%`);
  placeReset.hidden = state.at === null && state.scale === null;
  for (const axis of ['x', 'y'] as const) {
    const btn = placeCenter[axis];
    if (btn) btn.hidden = centerMotif(info, w, h, p, axis)[axis] === p[axis];
  }
}

/** Shows the motif at `p` on the live layers, starting them on the first move. */
function previewMotif(p: Placement): void {
  const info = motifInfo();
  if (!info || !motif) return;
  const [w, h] = CANVAS[state.aspect];
  preview = clampPlacement(info, w, h, p);
  if (!motif.live) {
    const svg = recolored(dataOf(state.variant), sourceAspect(), currentSeeds()).then((r) => r.svg);
    void motif.start(svg, info, preview);
  }
  renderMotif();
}

/** Takes the previewed placement into the state, which redraws the plate with it. */
function commitMotif(): void {
  if (!preview) return;
  const { x, y, k } = preview;
  preview = null;
  update({ at: [x, y], scale: k === 1 ? null : k });
}

const showThumbs = keyedShow();
/** Each version's 16:9 picture in the current theme. */
function renderThumbs(): void {
  const seeds = currentSeeds();
  showThumbs(tokenOf(seeds), () => {
    const stops = thumbs.map((t) =>
      keepShowing(t, dataOf(t.dataset.version ?? DEFAULT_VARIANT), '16:9', seeds),
    );
    return () => {
      for (const stop of stops) stop();
    };
  });
}

const showMap = keyedShow();
/** The crop map's 16:9 picture in the current version and theme. */
function renderMap(): void {
  const seeds = currentSeeds();
  showMap(`${state.variant} ${tokenOf(seeds)}`, () =>
    keepShowing(cropMap, dataOf(state.variant), '16:9', seeds),
  );
}

let stopSlots = () => {};
/** Reads the shown version's slots.json, its focus and cells, retrying a failed fetch. */
function loadSlots(): void {
  stopSlots();
  const url = dataOf(state.variant).slots;
  // Another version's slots would place its motif by the wrong template.
  if (url !== slotsUrl) slots = undefined;
  stopSlots = retrying(() =>
    getSlots(url).then((loaded) => {
      if (url !== dataOf(state.variant).slots) return;
      focus = Array.isArray(loaded.focus)
        ? [Number(loaded.focus[0]), Number(loaded.focus[1])]
        : [0.5, 0.5];
      cells = Array.isArray(loaded.cells) ? loaded.cells.map(Number).filter((c) => c > 0) : [];
      slots = loaded;
      slotsUrl = url;
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

// ---- motif ----

/** The placement with one of the motif's ranges at its value. */
function fromRanges(info: MotifInfo): Placement {
  const p = shownPlacement(info);
  const k = Number(placeK?.value) / (info.cell ?? 100);
  return { x: Number(placeX?.value ?? p.x), y: Number(placeY?.value ?? p.y), k };
}

for (const input of [placeX, placeY, placeK]) {
  input?.addEventListener('input', () => {
    const info = motifInfo();
    if (info) previewMotif(fromRanges(info));
  });
  input?.addEventListener('change', commitMotif);
}
/** Runs `act` on a click of `btn`, and moves focus to `range` when that hides the focused button. */
function keepFocus(btn: HTMLElement | null, range: HTMLInputElement | null, act: () => void): void {
  btn?.addEventListener('click', () => {
    const focused = document.activeElement === btn;
    act();
    if (focused && btn.hidden) range?.focus();
  });
}
keepFocus(placeReset, placeK, () => update({ at: null, scale: null }));
for (const [axis, range] of [
  ['x', placeX],
  ['y', placeY],
] as const) {
  keepFocus(placeCenter[axis], range, () => {
    const info = motifInfo();
    if (!info) return;
    const [w, h] = CANVAS[state.aspect];
    const { x, y } = centerMotif(info, w, h, shownPlacement(info), axis);
    update({ at: [x, y] });
  });
}

// Narrow screens show the motif's rows under the plate, wide ones in Export.
const motifRows = document.getElementById('motif-rows');
const motifHome = motifRows?.nextElementSibling;
const motifNear = document.querySelector('.motif-near');
function placeRows(): void {
  if (!motifRows || !motifHome || !motifNear) return;
  if (narrow.matches) motifNear.append(motifRows);
  else motifHome.before(motifRows);
}
placeRows();
narrow.addEventListener('change', placeRows);

/** The touches on the plate, by pointer id, in client pixels. */
const touches = new Map<number, [number, number]>();
/** The pinch in progress: the placement it began from, its fingers' midpoint and spread in canvas units. */
let pinch: { from: Placement; m0: [number, number]; d0: number } | undefined;
/** Stops the one-pointer drag in progress, which a pinch takes over. */
let stopDrag: (() => void) | undefined;

/** The first two touches' midpoint and distance, in canvas units. */
function fingers(): { m: [number, number]; d: number } | undefined {
  const [a, b] = touches.values();
  if (!motif || !a || !b) return undefined;
  const r = motif.canvas.getBoundingClientRect();
  const units = CANVAS[sourceAspect()][0] / r.width;
  const m: [number, number] = [
    ((a[0] + b[0]) / 2 - r.left) * units,
    ((a[1] + b[1]) / 2 - r.top) * units,
  ];
  return { m, d: Math.hypot(a[0] - b[0], a[1] - b[1]) * units };
}

// The handle moves the motif; a corner of it resizes the motif about the opposite corner.
motif?.handle.addEventListener('pointerdown', (e) => {
  const info = motifInfo();
  // A second finger joins the pinch the plate's listener starts.
  if (e.pointerType === 'touch' && touches.size > 0) return;
  if (e.button !== 0 || !info || !motif.canvas.clientWidth) return;
  e.preventDefault();
  if (e.pointerType !== 'mouse') motif.frame.dataset.touched = '';
  const [w, h] = CANVAS[sourceAspect()];
  const units = w / motif.canvas.clientWidth;
  const from = shownPlacement(info);
  const corner = (e.target as HTMLElement).closest<HTMLElement>('.motif-corner')?.dataset.corner;
  if (!corner) {
    const move = (dx: number, dy: number) =>
      previewMotif({ ...from, x: from.x + dx, y: from.y + dy });
    stopDrag = dragMotif(motif.handle, e, units, move, commitMotif);
    return;
  }
  const c = [Number(corner[0]), Number(corner[2])] as const;
  const [hx, hy, hw, hh] = info.handle;
  const [px, py] = [from.x + (hx + c[0] * hw) * from.k, from.y + (hy + c[1] * hh) * from.k];
  const resize = (dx: number, dy: number) =>
    previewMotif(resizeMotif(info, w, h, from, c, [px + dx, py + dy]));
  stopDrag = dragMotif(motif.handle, e, units, resize, commitMotif);
});

// Two fingers anywhere on the plate pinch the motif: its size follows their spread, and it moves with them.
if (motif) {
  plate.addEventListener('pointerdown', (e) => {
    const info = motifInfo();
    if (e.pointerType !== 'touch' || !info) return;
    touches.set(e.pointerId, [e.clientX, e.clientY]);
    const f = touches.size === 2 ? fingers() : undefined;
    if (!f) return;
    e.preventDefault();
    stopDrag?.();
    motif.frame.dataset.touched = '';
    pinch = { from: shownPlacement(info), m0: f.m, d0: f.d };
  });
  plate.addEventListener('pointermove', (e) => {
    if (!touches.has(e.pointerId)) return;
    touches.set(e.pointerId, [e.clientX, e.clientY]);
    const info = motifInfo();
    const f = fingers();
    if (!pinch || !info || !f) return;
    const [w, h] = CANVAS[sourceAspect()];
    previewMotif(pinchMotif(info, w, h, pinch.from, pinch.m0, pinch.d0, f.m, f.d));
  });
  const lift = (e: PointerEvent) => {
    if (!touches.delete(e.pointerId) || !pinch) return;
    pinch = undefined;
    commitMotif();
  };
  plate.addEventListener('pointerup', lift);
  plate.addEventListener('pointercancel', lift);
}
// On a touch screen the handle stays framed, with its corners, until a touch lands elsewhere.
document.addEventListener('pointerdown', (e) => {
  if (motif && !motif.handle.contains(e.target as Node)) delete motif.frame.dataset.touched;
});

const moveCrop = (t: number) => update({ crop: t });
const cropFrom = () => shapeOf(state, native, focus).t;

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
    dragCrop(win, e, state.aspect, cropFrom(), picture * (1 - cropSpan(state.aspect)), moveCrop);
  });
}

// A plate showing the crop itself moves the picture under it, so the crop runs against the drag.
plate.addEventListener('pointerdown', (e) => {
  const img = plate.querySelector<HTMLImageElement>(':scope > img[data-aspect="16:9"]');
  if (e.button !== 0 || !img || !cropsInPlace(shapeOf(state, native, focus))) return;
  e.preventDefault();
  const travel = (img.clientHeight * 16) / 9 - img.clientWidth;
  dragCrop(plate, e, state.aspect, cropFrom(), travel, moveCrop, true);
});

// ---- export ----

setUpExport({
  panel,
  buttons: downloadBtns,
  error: exportError,
  formatRadios,
  formatHint,
  slug,
  job: () => {
    const f = formatOf(parts);
    const shape = shapeOf(state, native, focus, motifInfo());
    const seeds = currentSeeds();
    const token = tokenOf(seeds);
    const asked = { ...state };
    const source = sourceAspect();
    const size = sizePx(state.size);
    const name = downloadName(
      slug,
      state.variant,
      token,
      f,
      `${size[0]}x${size[1]}`,
      state.aspect,
      !shape.native,
    );
    const data = dataOf(state.variant);
    return {
      variant: state.variant,
      data,
      source,
      shape,
      place: (loaded) => placementOf(asked, motifIn(loaded, source, seeds)),
      seeds,
      token,
      format: f,
      size,
      name,
    };
  },
  onFormatChange: render,
});

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
