/** The picker's themes: the presets of src/lib/theme.ts, named and grouped into families. */
import { DEFAULT_THEME, PRESETS, type Seeds } from './theme';

export interface Preset extends Seeds {
  name: string;
}

/** The theme pages are rendered in before the theme boot runs. */
export const DEFAULT_PRESET: Preset = { name: DEFAULT_THEME, ...PRESETS[DEFAULT_THEME] };

/** OKLab distance from bg or fg under which the picker warns that the accent will not stand out; every preset clears it. */
export const NEAR_ACCENT = 0.1;

/** A preset's swatch colors: bg, fg, accent. */
export function presetColors(name: string): readonly [string, string, string] {
  const p = PRESETS[name];
  return [p.bg, p.fg, p.accent];
}

/** Accessible name of the theme button (WCAG 2.5.3: starts with the visible name, "custom" when no preset matches). */
export function presetLabel(p: Preset): string {
  return `${p.name} theme: background ${p.bg}, foreground ${p.fg}, accent ${p.accent}`;
}

/**
 * The presets grouped by the scheme they come from, in picker order. A family with a `light` preset
 * can be chosen as a whole, showing `light` while the system prefers a light scheme and `dark`
 * otherwise; a family without one is just its `dark` preset.
 */
export interface Family {
  name: string;
  dark: string;
  light?: string;
}

export const FAMILIES: readonly Family[] = [
  { name: 'fireproof', dark: 'fireproof', light: 'flexoki-light' },
  { name: 'ayu', dark: 'ayu-dark', light: 'ayu-light' },
  { name: 'catppuccin', dark: 'catppuccin-mocha', light: 'catppuccin-latte' },
  { name: 'dracula', dark: 'dracula' },
  { name: 'everforest', dark: 'everforest-dark', light: 'everforest-light' },
  { name: 'gruvbox', dark: 'gruvbox-dark', light: 'gruvbox-light' },
  { name: 'nord', dark: 'nord' },
  { name: 'rose-pine', dark: 'rose-pine', light: 'rose-pine-dawn' },
  { name: 'solarized', dark: 'solarized-dark', light: 'solarized-light' },
  { name: 'tokyo-night', dark: 'tokyo-night', light: 'tokyo-night-day' },
];

/** The family nothing saved stands for: the site follows the system scheme with its two presets. */
export const DEFAULT_FAMILY = 'fireproof';

/** The family named `name` that has a light preset, or undefined. */
export function pairedFamily(name: string): Family | undefined {
  return FAMILIES.find((f) => f.name === name && f.light !== undefined);
}
