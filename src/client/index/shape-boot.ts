/**
 * The inline script at the top of the index's `section.plates` (index.astro bundles it): sets the
 * section's shape (markShape) and checks the matching Shape radio before first paint, so the grid does not
 * reflow when the page module loads. On any failure the grid stays 16:9 until then.
 */
import { aspectLabel, aspectOfLabel } from '../../lib/content';
import { deviceAspect, markShape } from '../screen';

try {
  const section = document.currentScript?.parentElement;
  const shape = aspectOfLabel(new URLSearchParams(location.search).get('shape')) ?? deviceAspect();
  if (section) markShape(section, 'shape', shape);
  const radio = document.querySelector<HTMLInputElement>(
    `#facets input[name=shape][value="${aspectLabel(shape)}"]`,
  );
  if (radio) radio.checked = true;
} catch {
  // The page module sets the shape when it loads.
}
