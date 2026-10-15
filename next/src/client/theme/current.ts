/** The theme the page is showing, for code outside React (the theme boot applies it before any of it runs). */
import { parseToken, type Seeds } from '../../lib/theme';
import { resolveTheme, THEME_EVENT } from './store';

/** The applied seeds: the token applyTheme() left in `<html data-theme>`, else the resolved theme. */
export function currentSeeds(): Seeds {
  return parseToken(document.documentElement.dataset.theme) ?? resolveTheme().seeds;
}

/** Calls `fn` with the new seeds after every applyTheme(); returns the unsubscribe. */
export function onThemeChange(fn: (seeds: Seeds) => void): () => void {
  const handler = () => fn(currentSeeds());
  document.addEventListener(THEME_EVENT, handler);
  return () => document.removeEventListener(THEME_EVENT, handler);
}
