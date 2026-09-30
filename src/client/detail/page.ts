/**
 * The detail page: versions and their pictures, plate, crop window, export panel and the Download
 * under the attribution, run command, the `f` key, "Copy" and the "See also" plates, shown in the page's
 * shape. On narrow screens a tall cropped shape shows the crop in the plate itself, with the crop
 * window on a small 16:9 map in the export panel.
 * A visitor's change goes through update(), which renders the whole page from the state and writes
 * the address; render() is cheap enough to run on every crop drag.
 */
import { type Aspect, CANVAS, DEFAULT_VARIANT, downloadName, isAspect } from '../../lib/content';
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
import { tokenOf } from '../../lib/theme';
import { copyText, flash } from '../clipboard';
import { must, readJson, replaceAddress } from '../dom';
import { plateGrid } from '../grid';
import { getSlots, keepShowing, keyedShow, type PlateData, plateData } from '../plates';
import { retrying } from '../retry';
import { markShape, NARROW_QUERY, screenPx } from '../screen';
import { currentSeeds, onThemeChange } from '../theme/current';
import { dragCrop, placeCrop } from './crop';
import { setUpExport } from './export';
import { allowed, formatOf, panelParts, renderPanel, sizePx, startState } from './panel';
import { type DetailState, keptCrop, shapeOf, sizeFor, writeAddress } from './state';

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

const showPlate = keyedShow();
function renderPlate(): void {
  const seeds = currentSeeds();
  showPlate(`${state.variant} ${sourceAspect()} ${tokenOf(seeds)}`, () =>
    keepShowing(plate, dataOf(state.variant), sourceAspect(), seeds),
  );
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
    const shape = shapeOf(state, native, focus);
    const seeds = currentSeeds();
    const token = tokenOf(seeds);
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
      source: sourceAspect(),
      shape,
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
