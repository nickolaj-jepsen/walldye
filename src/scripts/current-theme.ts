/** The theme the page is showing, for the page modules (the theme boot applies it before they load). */
import { normaliseSeed, type Seeds } from '../lib/theme';
import { resolveTheme, THEME_EVENT } from '../lib/theme-store';

/** The applied seeds: the `--seed-*` properties applyTheme() set on <html>, else the resolved theme. */
export function currentSeeds(): Seeds {
  const style = document.documentElement.style;
  const bg = normaliseSeed(style.getPropertyValue('--seed-bg'));
  const fg = normaliseSeed(style.getPropertyValue('--seed-fg'));
  const accent = normaliseSeed(style.getPropertyValue('--seed-accent'));
  return bg && fg && accent ? { bg, fg, accent } : resolveTheme().seeds;
}

/** Calls `fn` with the new seeds after every applyTheme(). */
export function onThemeChange(fn: (seeds: Seeds) => void): void {
  document.addEventListener(THEME_EVENT, () => fn(currentSeeds()));
}
