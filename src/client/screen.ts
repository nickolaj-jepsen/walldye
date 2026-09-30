/** The visitor's screen: its size at device resolution and the shape plates start in. */
import { type Aspect, CANVAS } from '../lib/content';
import { nearestAspect, withinLimits } from '../lib/shape';

/** Narrow screens, where site.css stacks the page; keep the width in step with its 60rem break. */
export const NARROW_QUERY = '(max-width: 60rem)';
/** Wide screens, the rest. */
export const WIDE_QUERY = '(min-width: 60.0625rem)';
/** Phones and small tablets, which start on their own screen's shape. */
export const PHONE_QUERY = `${NARROW_QUERY} and (pointer: coarse)`;

export function isPhone(): boolean {
  return matchMedia(PHONE_QUERY).matches;
}

/** The screen in output pixels: its CSS size times the device pixel ratio. */
export function screenPx(): [number, number] {
  const dpr = devicePixelRatio || 1;
  return [Math.round(screen.width * dpr), Math.round(screen.height * dpr)];
}

/** The shape a page shows before the visitor picks one: the screen's nearest on a phone, else 16:9. */
export function deviceAspect(): Aspect {
  return isPhone() ? nearestAspect(...screenPx()) : '16:9';
}

/** The detail page's first shape: the screen's nearest, unless the screen is too large to draw at its size. */
export function exportAspect(): Aspect {
  const px = screenPx();
  return withinLimits(...px) ? nearestAspect(...px) : '16:9';
}

/**
 * Marks `el` as showing `shape` for site.css: `data-<attr>` names it, `--shape-ratio` is its width
 * over height, and `data-tall` is set when it is taller than wide.
 */
export function markShape(el: HTMLElement, attr: 'shape' | 'aspect', shape: Aspect): void {
  const [w, h] = CANVAS[shape];
  el.dataset[attr] = shape;
  el.style.setProperty('--shape-ratio', String(w / h));
  el.toggleAttribute('data-tall', h > w);
}
