/** The picker's theme list as the server renders it, from src/lib/theme.ts in walldye.PRESETS order. */
import { DEFAULT_THEME, PRESETS as THEME_PRESETS, type Seeds } from '../lib/theme';

export interface Preset extends Seeds {
  name: string;
}

export const PRESETS: readonly Preset[] = Object.entries(THEME_PRESETS).map(([name, seeds]) => ({ name, ...seeds }));

/** The theme pages are rendered in before the theme boot runs. */
export const DEFAULT_PRESET: Preset = PRESETS.find((p) => p.name === DEFAULT_THEME)!;

/** Accessible name of the theme button (WCAG 2.5.3: starts with the visible name, "custom" when no preset matches). */
export function presetLabel(p: Preset): string {
  return `${p.name} theme: background ${p.bg}, foreground ${p.fg}, accent ${p.accent}`;
}
