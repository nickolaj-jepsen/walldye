/** The custom editor's warnings about colors that will not read well in wallpapers. */
import { NEAR_ACCENT } from '../../lib/presets';
import { contrast, distance, normalizeSeed, type Seed } from '../../lib/theme';

/** Raw bg/fg contrast under which the picker warns that wallpapers will be hard to see. */
export const FAINT = 3;

export interface Warnings {
  /** bg and fg are too close. */
  faint: boolean;
  /** The accent is too close to bg. */
  nearBg: boolean;
  /** The accent is too close to fg; never set together with nearBg. */
  nearFg: boolean;
}

/** The warnings for the fields' text; a field that holds no valid color raises none. */
export function warningsFor(texts: Readonly<Record<Seed, string>>): Warnings {
  const bg = normalizeSeed(texts.bg);
  const fg = normalizeSeed(texts.fg);
  const accent = normalizeSeed(texts.accent);
  const faint = bg !== null && fg !== null && contrast(bg, fg) < FAINT;
  // One accent warning at a time; vanishing into the ground is the worse of the two.
  const nearBg = bg !== null && accent !== null && distance(accent, bg) < NEAR_ACCENT;
  const nearFg = !nearBg && fg !== null && accent !== null && distance(accent, fg) < NEAR_ACCENT;
  return { faint, nearBg, nearFg };
}
