/** The custom editor's live preview: the theme's custom properties without saving or announcing it. */
import { seedVars } from '../../lib/seed-vars';
import { cssVars, parseToken, regimeOf, type Seeds } from '../../lib/theme';

function paint(seeds: Seeds): void {
  const root = document.documentElement;
  const vars = { ...cssVars(seeds), ...seedVars(seeds) };
  for (const [prop, value] of Object.entries(vars)) root.style.setProperty(prop, value);
  root.dataset.regime = regimeOf(seeds);
}

/**
 * Repaints the site and every plate in `seeds` through the `<html>` custom properties and
 * `data-regime`, leaving `data-theme`, storage, the favicon and THEME_EVENT alone, so the applied
 * theme is still the one applyTheme() last set.
 */
export function previewTheme(seeds: Seeds): void {
  paint(seeds);
}

/** Puts back the applied theme's properties (`<html data-theme>`) after previewTheme(). */
export function endPreview(): void {
  const seeds = parseToken(document.documentElement.dataset.theme);
  if (seeds) paint(seeds);
}
