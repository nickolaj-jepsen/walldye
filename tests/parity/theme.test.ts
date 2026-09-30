import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { isLight, PRESETS, parseToken, type Seeds, themeTokens } from '../../src/lib/theme';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));

interface Entry {
  seeds: Seeds;
  light: boolean;
  tokens: Record<string, string>;
}

describe('derive_theme (c)', () => {
  const text = readFileSync(`${ROOT}tests/fixtures/themes.json`, 'utf8');
  const fixture = JSON.parse(text) as { random: Record<'dark' | 'light', Entry[]>; edges: Entry[] };
  const entry = (seeds: Seeds): Entry => ({
    seeds,
    light: isLight(seeds.bg, seeds.fg),
    tokens: themeTokens(seeds),
  });

  it('is byte-equal to themes.json from regen.py', () => {
    const built = {
      presets: Object.fromEntries(
        Object.keys(PRESETS).map((name) => [name, entry(parseToken(name) as Seeds)]),
      ),
      random: {
        dark: fixture.random.dark.map((e) => entry(e.seeds)),
        light: fixture.random.light.map((e) => entry(e.seeds)),
      },
      edges: fixture.edges.map((e) => entry(e.seeds)),
    };
    expect(`${JSON.stringify(built, null, 2)}\n`).toBe(text);
  });

  it('covers both regimes with at least 20 triples each', () => {
    expect(fixture.random.dark.length).toBeGreaterThanOrEqual(20);
    expect(fixture.random.light.length).toBeGreaterThanOrEqual(20);
    expect(fixture.random.dark.every((e) => !e.light)).toBe(true);
    expect(fixture.random.light.every((e) => e.light)).toBe(true);
  });
});
