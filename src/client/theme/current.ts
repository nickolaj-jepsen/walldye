/** The theme the page is showing, for the page modules (the theme boot applies it before they load). */
import { parseToken, type Seeds } from '../../lib/theme';
import { resolveTheme, THEME_EVENT } from './store';

/** The applied seeds: the token applyTheme() left in `<html data-theme>`, else the resolved theme. */
export function currentSeeds(): Seeds {
  return parseToken(document.documentElement.dataset.theme) ?? resolveTheme().seeds;
}

/** Calls `fn` with the new seeds after every applyTheme(). */
export function onThemeChange(fn: (seeds: Seeds) => void): void {
  document.addEventListener(THEME_EVENT, () => fn(currentSeeds()));
}
