import { describe, expect, it } from 'vitest';
import {
  DEFAULT_FAMILY,
  FAMILIES,
  NEAR_ACCENT,
  pairedFamily,
  presetColors,
  SYSTEM_PAIR,
} from '../../src/lib/presets';
import { DEFAULT_THEME, distance, PRESETS, regimeOf } from '../../src/lib/theme';

describe('families', () => {
  it('hold every preset once, a dark one first and a light one second', () => {
    const members = FAMILIES.flatMap((f) => (f.light ? [f.dark, f.light] : [f.dark]));
    expect([...members].sort()).toEqual(Object.keys(PRESETS).sort());
    for (const f of FAMILIES) {
      expect(regimeOf(PRESETS[f.dark])).toBe('dark');
      if (f.light) expect(regimeOf(PRESETS[f.light])).toBe('light');
    }
    expect(new Set(FAMILIES.map((f) => f.name)).size).toBe(FAMILIES.length);
  });

  it('start with the default, the pair the theme store falls back to', () => {
    const f = pairedFamily(DEFAULT_FAMILY);
    expect(FAMILIES[0].name).toBe(DEFAULT_FAMILY);
    expect(f?.dark).toBe(DEFAULT_THEME);
    expect([f?.dark, f?.light]).toEqual(SYSTEM_PAIR);
  });

  it('are paired only when they have a light theme', () => {
    expect(pairedFamily('gruvbox')).toMatchObject({ dark: 'gruvbox-dark', light: 'gruvbox-light' });
    expect(pairedFamily('nord')).toBeUndefined();
    expect(pairedFamily('gruvbox-dark')).toBeUndefined();
  });
});

describe('presets', () => {
  it('keep the accent clear of bg and fg, so the picker never warns about one', () => {
    for (const name of Object.keys(PRESETS)) {
      const [bg, fg, accent] = presetColors(name);
      expect(distance(accent, bg), name).toBeGreaterThanOrEqual(NEAR_ACCENT);
      expect(distance(accent, fg), name).toBeGreaterThanOrEqual(NEAR_ACCENT);
    }
  });
});
