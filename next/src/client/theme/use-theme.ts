/**
 * The applied theme for client components: the token applyTheme() leaves on `<html data-theme>`,
 * read through useSyncExternalStore so every reader re-renders after each applyTheme(). During
 * server rendering and hydration the theme is unknown (null), since only the browser knows it.
 */
import { useSyncExternalStore } from 'react';
import { parseToken, type Regime, regimeOf, type Seeds } from '../../lib/theme';
import { applyTheme, saveTheme, THEME_EVENT } from './store';

export interface AppliedTheme {
  /** Canonical token: a preset name or `bg-fg-accent`. */
  token: string;
  seeds: Seeds;
  regime: Regime;
}

function subscribe(onChange: () => void): () => void {
  document.addEventListener(THEME_EVENT, onChange);
  return () => document.removeEventListener(THEME_EVENT, onChange);
}

const token = () => document.documentElement.dataset.theme ?? null;
const unknown = () => null;

/** The applied theme token, or null before hydration. */
export function useThemeToken(): string | null {
  return useSyncExternalStore(subscribe, token, unknown);
}

/** The applied theme, or null before hydration (and if the boot failed). */
export function useTheme(): AppliedTheme | null {
  const t = useThemeToken();
  const seeds = parseToken(t);
  return t && seeds ? { token: t, seeds, regime: regimeOf(seeds) } : null;
}

/** The applied regime, or null before hydration. */
export function useRegime(): Regime | null {
  return useTheme()?.regime ?? null;
}

/** Applies `seeds` live and saves them as the visitor's own theme, ending any shared one. */
export function chooseTheme(seeds: Seeds): void {
  saveTheme(seeds);
  applyTheme(seeds);
}
