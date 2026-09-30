/**
 * The inline script after the detail page's controls ([slug].astro bundles it): renders the export
 * panel and both Download summaries in the start state before first paint, so a screen that is not
 * 16:9 does not see their text change when the page module loads. On any failure they keep the
 * server's 16:9 until then.
 */
import { must, readJson } from '../dom';
import { panelParts, renderPanel, startState } from './panel';

try {
  const versions = readJson<Record<string, unknown>>(must('.spread .plate'), 'variants', {});
  renderPanel(panelParts(), startState(Object.keys(versions)));
} catch {
  // The page module renders them when it loads.
}
