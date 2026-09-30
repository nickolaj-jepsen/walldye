/**
 * The inline script at the top of the detail page's `.spread` ([slug].astro bundles it): sets its
 * shape (markShape) to the one the page starts in before first paint, so a phone's tall plate does not
 * grow when the page module loads. On any failure the plate stays 16:9 until then.
 */
import { markShape } from '../screen';
import { startAspect } from './panel';

try {
  const spread = document.currentScript?.parentElement;
  if (spread) markShape(spread, 'aspect', startAspect());
} catch {
  // The page module sets the shape when it loads.
}
