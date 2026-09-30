/**
 * Where the visitor's theme comes from and where it is kept:
 * a shared `?t=` token for the session, then the saved theme, then the system color scheme.
 * sessionStorage holds a canonical theme token; localStorage holds one too, or `pair:<dark>,<light>`,
 * two tokens of which the system scheme picks one. Every storage access is guarded. When a storage
 * cannot be written, the value is kept on `<html>` (PAGE_ATTR) instead, so it holds for the rest of
 * the page and is visible to every bundle that imports this module.
 */

import { faviconUrl } from '../../lib/favicon';
import { type Pair, SYSTEM_PAIR } from '../../lib/presets';
import { cssVars, parseToken, regimeOf, type Seeds, tokenOf } from '../../lib/theme';

export const STORAGE_KEY = 'walldye.theme';
/** Dispatched on `document` after applyTheme(); `detail` is the applied theme's canonical token. */
export const THEME_EVENT = 'walldye:theme';
const LIGHT_QUERY = '(prefers-color-scheme: light)';
const PAIR_PREFIX = 'pair:';

export type ThemeSource = 'shared' | 'saved' | 'system';
export interface ResolvedTheme {
  token: string;
  seeds: Seeds;
  source: ThemeSource;
}

type Store = 'sessionStorage' | 'localStorage';

/** `<html>` dataset keys standing in for each storage when it cannot be written. */
export const PAGE_ATTR: Readonly<Record<Store, string>> = {
  sessionStorage: 'themeShared',
  localStorage: 'themeSaved',
};

function pageData(): Record<string, string | undefined> {
  return globalThis.document.documentElement.dataset;
}

function read(store: Store): string | null {
  // Set only when the last write failed, so it is newer than whatever the storage still holds.
  const kept = pageData()[PAGE_ATTR[store]];
  if (kept !== undefined) return kept;
  try {
    return globalThis[store].getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function write(store: Store, token: string | null): void {
  const data = pageData();
  delete data[PAGE_ATTR[store]];
  try {
    if (token === null) globalThis[store].removeItem(STORAGE_KEY);
    else globalThis[store].setItem(STORAGE_KEY, token);
  } catch {
    // Storage blocked or full: keep the token on the page, so it still applies until the visitor leaves it.
    if (token !== null) data[PAGE_ATTR[store]] = token;
  }
}

function resolved(seeds: Seeds, source: ThemeSource): ResolvedTheme {
  return { token: tokenOf(seeds), seeds, source };
}

function systemLight(): boolean {
  try {
    return globalThis.matchMedia(LIGHT_QUERY).matches;
  } catch {
    return false;
  }
}

/** The seeds `pair` shows under the system scheme; both tokens must parse. */
function pairSeeds(pair: Pair): Seeds {
  return parseToken(pair[systemLight() ? 1 : 0]) as Seeds;
}

/** The pair a localStorage value holds, as canonical tokens, or null. */
function storedPair(value: string | null): Pair | null {
  if (!value?.startsWith(PAIR_PREFIX)) return null;
  const [dark, light, ...rest] = value.slice(PAIR_PREFIX.length).split(',').map(parseToken);
  return dark && light && !rest.length ? [tokenOf(dark), tokenOf(light)] : null;
}

export function sharedTheme(): ResolvedTheme | null {
  const seeds = parseToken(read('sessionStorage'));
  return seeds && resolved(seeds, 'shared');
}

/**
 * What the visitor chose, ignoring any shared theme: `{ pair }` for a pair that follows the system
 * scheme (SYSTEM_PAIR when nothing valid is saved), else `{ token }` of a fixed theme.
 */
export function ownChoice(): { pair: Pair } | { token: string } {
  const value = read('localStorage');
  const pair = storedPair(value);
  if (pair) return { pair };
  const seeds = parseToken(value);
  return seeds ? { token: tokenOf(seeds) } : { pair: SYSTEM_PAIR };
}

export function savedTheme(): ResolvedTheme | null {
  const value = read('localStorage');
  const pair = storedPair(value);
  if (pair) return resolved(pairSeeds(pair), 'saved');
  const seeds = parseToken(value);
  return seeds && resolved(seeds, 'saved');
}

/** SYSTEM_PAIR's theme for the system scheme: fireproof, or flexoki-light under a light one. */
export function systemTheme(): ResolvedTheme {
  return resolved(pairSeeds(SYSTEM_PAIR), 'system');
}

/** The visitor's own theme, ignoring any shared one: saved, else the system's. */
export function ownTheme(): ResolvedTheme {
  return savedTheme() ?? systemTheme();
}

/** The theme to show: the session's shared theme, else ownTheme(). */
export function resolveTheme(): ResolvedTheme {
  return sharedTheme() ?? ownTheme();
}

/** Whether a shared theme is in effect that differs from the visitor's own (the header offers Keep it / Back to yours). */
export function sharedDiffers(): boolean {
  const shared = sharedTheme();
  return shared !== null && shared.token !== ownTheme().token;
}

/**
 * Reads `?t=` once: a valid token becomes the session's shared theme (invalid ones are ignored), and
 * the parameter is stripped from the address with history.replaceState either way.
 */
export function takeSharedParam(): void {
  const url = new URL(globalThis.location.href);
  const value = url.searchParams.get('t');
  if (value === null) return;
  const seeds = parseToken(value);
  if (seeds) write('sessionStorage', tokenOf(seeds));
  url.searchParams.delete('t');
  globalThis.history.replaceState(globalThis.history.state, '', url.href);
}

/** Saves `seeds` as the visitor's theme and ends any shared theme. Does not apply it. */
export function saveTheme(seeds: Seeds): void {
  write('localStorage', tokenOf(seeds));
  write('sessionStorage', null);
}

/**
 * Saves `pair` (two theme tokens) as the visitor's theme, to follow the system scheme, and ends any
 * shared theme; SYSTEM_PAIR clears the saved theme instead, so nothing is saved. Does not apply it.
 * Throws when a token does not parse.
 */
export function savePair(pair: Pair): void {
  const [dark, light] = pair.map(parseToken);
  if (!dark || !light) throw new Error(`bad theme pair ${pair.join(',')}`);
  const value = `${PAIR_PREFIX}${tokenOf(dark)},${tokenOf(light)}`;
  write('localStorage', value === `${PAIR_PREFIX}${SYSTEM_PAIR.join(',')}` ? null : value);
  write('sessionStorage', null);
}

/** Ends the session's shared theme. Does not apply anything. */
export function clearShared(): void {
  write('sessionStorage', null);
}

/**
 * Sets every site color property (cssVars) inline on <html>, plus `data-regime` and `data-theme`
 * (the canonical token, which currentSeeds() reads back), points `#favicon` at the icon in `seeds`,
 * then dispatches THEME_EVENT.
 */
export function applyTheme(seeds: Seeds): void {
  const root = globalThis.document.documentElement;
  const token = tokenOf(seeds);
  for (const [prop, value] of Object.entries(cssVars(seeds))) root.style.setProperty(prop, value);
  root.dataset.regime = regimeOf(seeds);
  root.dataset.theme = token;
  globalThis.document.getElementById('favicon')?.setAttribute('href', faviconUrl(seeds));
  globalThis.document.dispatchEvent(new CustomEvent(THEME_EVENT, { detail: token }));
}

/**
 * Re-resolves and applies the theme when the system color scheme changes and when the page comes back
 * from the back/forward cache, where storage may have changed meanwhile. It applies even when the theme
 * is unchanged, so THEME_EVENT listeners re-check what depends on the system theme (the shared-theme line).
 */
export function followChanges(): void {
  const again = () => applyTheme(resolveTheme().seeds);
  try {
    globalThis.matchMedia(LIGHT_QUERY).addEventListener('change', again);
  } catch {
    // No matchMedia: nothing to follow.
  }
  globalThis.addEventListener?.('pageshow', (e) => {
    if ((e as PageTransitionEvent).persisted) again();
  });
}
