/**
 * The inline <head> script (inlineScript bundles it): applies the visitor's theme before
 * first paint and again whenever it may have changed (followChanges). On any failure the page keeps
 * site.css's no-JS theme.
 */

import { applyTheme, followChanges, resolveTheme, takeSharedParam } from './store';

try {
  takeSharedParam();
} catch {
  // An address that cannot be rewritten still gets a theme.
}
try {
  applyTheme(resolveTheme().seeds);
  followChanges();
} catch {
  // Leave the stylesheet's fallback theme in place.
}
