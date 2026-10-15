/**
 * The visitor's theme choice for the picker and the index's theme row: which theme or family shows
 * as pressed, whether a shared theme is showing, and the actions that change them. Every hook reads
 * storage, so during server rendering and hydration it reports the default: nothing shared and the
 * system pair's family pressed.
 */
import { useSyncExternalStore } from 'react';
import { FAMILIES, type Pair, pairedFamily, SYSTEM_PAIR } from '../../lib/presets';
import { PRESETS } from '../../lib/theme';
import {
  applyTheme,
  clearShared,
  ownChoice,
  ownTheme,
  savePair,
  saveTheme,
  sharedDiffers,
  sharedTheme,
  THEME_EVENT,
} from './store';

/** The pressed entry: a theme by token, or a family by name; at most one is set. */
export interface Pressed {
  preset: string | null;
  family: string | null;
}

/** What `choice` presses: its token, or the family whose two themes are its pair. */
export function pressedOf(choice: { pair: Pair } | { token: string }): Pressed {
  if ('token' in choice) return { preset: choice.token, family: null };
  const [dark, light] = choice.pair;
  const f = FAMILIES.find((x) => x.dark === dark && x.light === light);
  return { preset: null, family: f?.name ?? null };
}

function subscribe(onChange: () => void): () => void {
  document.addEventListener(THEME_EVENT, onChange);
  return () => document.removeEventListener(THEME_EVENT, onChange);
}

// Snapshots are strings so useSyncExternalStore sees a stable value between theme changes.
function choiceKey(): string {
  // A shared theme that differs from the visitor's own presses the theme it shows.
  if (sharedDiffers()) return `token:${document.documentElement.dataset.theme ?? ''}`;
  const choice = ownChoice();
  return 'token' in choice ? `token:${choice.token}` : `pair:${choice.pair.join(',')}`;
}

const defaultKey = () => `pair:${SYSTEM_PAIR.join(',')}`;

function parseKey(key: string): Pressed {
  if (key.startsWith('token:')) return pressedOf({ token: key.slice('token:'.length) });
  const [dark = '', light = ''] = key.slice('pair:'.length).split(',');
  return pressedOf({ pair: [dark, light] });
}

/**
 * The pressed theme or family: the visitor's choice, a fixed theme or a family, unless a shared
 * theme that differs from it is showing.
 */
export function usePressed(): Pressed {
  return parseKey(useSyncExternalStore(subscribe, choiceKey, defaultKey));
}

const noShared = () => false;

/** Whether a shared theme that differs from the visitor's own is showing (Keep it / Back to yours). */
export function useSharedDiffers(): boolean {
  return useSyncExternalStore(subscribe, sharedDiffers, noShared);
}

/** Applies and saves the preset `name` as the visitor's theme, ending any shared one; ignores unknown names. */
export function choosePreset(name: string): void {
  if (!Object.hasOwn(PRESETS, name)) return;
  const seeds = { ...PRESETS[name] };
  saveTheme(seeds);
  applyTheme(seeds);
}

/**
 * Saves the family `name` to follow the system scheme, ending any shared theme, and applies the
 * theme it shows now; ignores names without a light theme.
 */
export function chooseFamily(name: string): void {
  const f = pairedFamily(name);
  if (!f?.light) return;
  savePair([f.dark, f.light]);
  applyTheme(ownTheme().seeds);
}

/** Saves the shared theme as the visitor's own, so the shared line goes. */
export function keepShared(): void {
  const shared = sharedTheme();
  if (!shared) return;
  saveTheme(shared.seeds);
  // Same colors; applying again tells every reader the choice changed.
  applyTheme(shared.seeds);
}

/** Ends the shared theme and applies the visitor's own. */
export function dropShared(): void {
  clearShared();
  applyTheme(ownTheme().seeds);
}
