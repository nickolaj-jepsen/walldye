/**
 * The detail page's start state and the text parts of its render (the export panel's Shape and Size
 * rows and both Download summaries), shared by the page module and the panel boot so the first paint
 * already shows the start state.
 */
import { type Aspect, DEFAULT_VARIANT, FORMATS } from '../../lib/content';
import { nearestAspect, withinLimits } from '../../lib/shape';
import { must } from '../dom';
import { exportAspect, screenPx } from '../screen';
import { type DetailState, readAddress, sizeFor } from './state';

export type Format = (typeof FORMATS)[number];

/** Output pixels of a size radio's value. */
export function sizePx(size: string): [number, number] {
  if (size === 'screen') return screenPx();
  const [w, h] = size.split('x').map(Number);
  return [w, h];
}

/** Whether this browser can draw a file at a size radio's value. */
export const allowed = (size: string): boolean => withinLimits(...sizePx(size));

/** The shape the page starts in: the address's, else the screen's (`exportAspect()`). */
export function startAspect(): Aspect {
  return readAddress(new URLSearchParams(location.search)).aspect ?? exportAspect();
}

/** The state the page starts in; `versions` names the versions on the page, the default included. */
export function startState(versions: readonly string[]): DetailState {
  const asked = readAddress(new URLSearchParams(location.search));
  // An unknown version, or a draft one outside `astro dev`, is not in `versions`: the default stays.
  const variant =
    asked.variant && versions.includes(asked.variant) ? asked.variant : DEFAULT_VARIANT;
  const aspect = startAspect();
  const keep = aspect === nearestAspect(...screenPx()) ? 'screen' : '';
  return { variant, aspect, crop: asked.crop ?? null, size: sizeFor(aspect, keep, allowed) };
}

/** The panel's hooks; throws when one is missing. */
export function panelParts() {
  const panel = must('#export');
  const aspectRadios = [...panel.querySelectorAll<HTMLInputElement>('input[name=asp]')];
  const buttons = [
    must<HTMLButtonElement>('#download'),
    must<HTMLButtonElement>('#quick-download'),
  ];
  const summary = (part: string) => buttons.map((btn) => must(`[data-part=${part}]`, btn));
  return {
    panel,
    buttons,
    aspectRadios,
    native: new Set(aspectRadios.filter((r) => r.hasAttribute('data-native')).map((r) => r.value)),
    sizes: [...must('#sizes').querySelectorAll('label')].map((label) => ({
      label,
      input: must<HTMLInputElement>('input', label),
    })),
    sizeLimit: must('#size-limit'),
    formatRadios: [...panel.querySelectorAll<HTMLInputElement>('input[name=fmt]')],
    summaryFormats: summary('format'),
    summarySizes: summary('size'),
  };
}
export type PanelParts = ReturnType<typeof panelParts>;

/** The checked format, PNG when none is. */
export function formatOf(p: PanelParts): Format {
  const v = p.formatRadios.find((r) => r.checked)?.value;
  return FORMATS.find((f) => f.value === v) ?? FORMATS[1];
}

/** Renders the Shape and Size rows and the Download summaries for `s`. */
export function renderPanel(p: PanelParts, s: DetailState): void {
  for (const r of p.aspectRadios) r.checked = r.value === s.aspect;

  let limited = false;
  for (const { label, input } of p.sizes) {
    const offered = input.value === 'screen' || label.dataset.aspect === s.aspect;
    const ok = allowed(input.value);
    label.hidden = !offered;
    input.disabled = !offered || !ok;
    input.checked = input.value === s.size;
    if (offered && !ok) {
      input.setAttribute('aria-describedby', 'size-limit');
      limited = true;
    } else {
      input.removeAttribute('aria-describedby');
    }
  }
  p.sizeLimit.hidden = !limited;

  const f = formatOf(p);
  const [w, h] = sizePx(s.size);
  for (const el of p.summaryFormats) el.textContent = f.label;
  // An SVG has a shape but no pixel size.
  for (const el of p.summarySizes) el.textContent = f.value === 'svg' ? s.aspect : `${w}×${h}`;
}
