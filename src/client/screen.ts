/** The visitor's screen: its size at device resolution and the shape plates start in. */
import type { Aspect } from '../lib/content';
import { nearestAspect, withinLimits } from './export/shape';

/** Phones and small tablets, which start on their own screen's shape. */
export const PHONE_QUERY = '(max-width: 60rem) and (pointer: coarse)';

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
