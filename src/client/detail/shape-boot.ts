/**
 * The inline script at the top of the detail page's `.spread` ([slug].astro bundles it): sets its
 * `data-aspect` to the shape the page starts in before first paint, so a phone's tall plate does not
 * grow when the page module loads. On any failure the plate stays 16:9 until then.
 */
import { aspectOfLabel } from '../../lib/content';
import { exportAspect } from '../screen';

try {
  const spread = document.currentScript?.parentElement;
  const shape = aspectOfLabel(new URLSearchParams(location.search).get('shape')) ?? exportAspect();
  if (spread) spread.dataset.aspect = shape;
} catch {
  // The page module sets the shape when it loads.
}
