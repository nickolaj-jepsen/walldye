/**
 * The index's two inline scripts, run while the prerendered page parses so it does not reflow when
 * React takes over: the filter starts closed on phones, and the grid takes its shape.
 */

import { PHONE_QUERY, WIDE_QUERY } from '../../client/screen';
import { SITE_ASPECTS } from '../../lib/content';
import { ratioOf } from '../../lib/shape';

interface ShapeBootConfig {
  phone: string;
  /** Each site aspect with its width over height, in SITE_ASPECTS order. */
  aspects: readonly (readonly [string, number])[];
}

/**
 * Runs as the first child of `section.plates`: sets the section's shape as markShape() would (the
 * `?shape=` one, else deviceAspect()'s), checks the matching Shape radio, and lets the plates drawn
 * in 16:9 fill their new boxes. Stringified, so it may use nothing but its argument and globals.
 */
function shapeBoot(c: ShapeBootConfig): void {
  try {
    const section = document.currentScript?.parentElement;
    const asked = new URLSearchParams(location.search).get('shape')?.replace('x', ':');
    let shape = c.aspects.find((a) => a[0] === asked);
    if (!shape) {
      shape = c.aspects[0];
      if (matchMedia(c.phone).matches) {
        const dpr = devicePixelRatio || 1;
        const r = Math.log(Math.round(screen.width * dpr) / Math.round(screen.height * dpr));
        let gap = Infinity;
        for (const a of c.aspects) {
          const d = Math.abs(r - Math.log(a[1]));
          if (d < gap - 1e-12) {
            shape = a;
            gap = d;
          }
        }
      }
    }
    if (!section || shape === c.aspects[0]) return;
    section.dataset.shape = shape[0];
    section.style.setProperty('--shape-ratio', String(shape[1]));
    section.toggleAttribute('data-tall', shape[1] < 1);
    const radio = document.querySelector<HTMLInputElement>(
      `#facets input[name=shape][value="${shape[0].replace(':', 'x')}"]`,
    );
    if (radio) radio.checked = true;
    for (const pic of section.querySelectorAll('.pic')) {
      pic.setAttribute('preserveAspectRatio', 'xMidYMid slice');
    }
  } catch {
    // React sets the shape when it renders.
  }
}

/** The shape boot as inline script text. */
export const SHAPE_BOOT = `(${shapeBoot.toString()})(${JSON.stringify({
  phone: PHONE_QUERY,
  aspects: SITE_ASPECTS.map((a) => [a, ratioOf(a)]),
} satisfies ShapeBootConfig)})`;

/** Runs right after the filter's `<details>`: closes it on narrow screens. */
export const FILTER_BOOT = `document.currentScript.previousElementSibling.open=matchMedia(${JSON.stringify(WIDE_QUERY)}).matches`;
