import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  contrast,
  cssVars,
  DIM,
  deriveTheme,
  distance,
  FIREPROOF,
  GUARDED,
  guard,
  isLight,
  luminance,
  mix,
  normalizeSeed,
  normalizeSeeds,
  PRESETS,
  parseToken,
  presetOf,
  roundHalfEven,
  type Seeds,
  TOKENS,
  themeTokens,
  tokenOf,
} from '../../src/lib/theme';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const FIXTURES = `${ROOT}src/lib/__fixtures__/`;

interface Entry {
  seeds: Seeds;
  light: boolean;
  tokens: Record<string, string>;
}

/** Deterministic PRNG (mulberry32) so the random triples are the same on every run. */
function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function randomSeeds(count: number, seed = 20260927): Seeds[] {
  const next = rng(seed);
  const hex = () =>
    `#${Math.floor(next() * 0x1000000)
      .toString(16)
      .padStart(6, '0')
      .toUpperCase()}`;
  return Array.from({ length: count }, () =>
    normalizeSeeds({ bg: hex(), fg: hex(), accent: hex() }),
  );
}

describe('number helpers', () => {
  it('rounds half to even like Python', () => {
    expect([0.5, 1.5, 2.5, 66.5, -0.5, -1.5, 2.4999, 2.5001].map(roundHalfEven)).toEqual([
      0, 2, 2, 66, 0, -2, 2, 3,
    ]);
  });

  it('mixes with half-even rounding: derived accent_3 of the fireproof seeds is #764233', () => {
    expect(mix('#CF6A4C', '#1C1B1A', 0.5)).toBe('#764233');
    expect(deriveTheme({ ...PRESETS.fireproof }).accent_3).toBe('#764233');
  });

  it('measures OKLab distance: 0 for equal colors, 1 from black to white, symmetric', () => {
    expect(distance('#CF6A4C', '#cf6a4c')).toBe(0);
    expect(distance('#000000', '#FFFFFF')).toBeCloseTo(1, 6);
    expect(distance('#191724', '#EBBCBA')).toBeCloseTo(distance('#EBBCBA', '#191724'), 12);
    // rose-pine's old accent next to its fg, close enough for the picker's warning.
    expect(distance('#EBBCBA', '#E0DEF4')).toBeLessThan(0.1);
  });

  it('treats equal luminance as dark', () => {
    expect(isLight('#808080', '#808080')).toBe(false);
    expect(isLight('#787878', '#777777')).toBe(true);
    expect(isLight('#777777', '#787878')).toBe(false);
  });
});

describe('derive_theme (c)', () => {
  const text = readFileSync(`${FIXTURES}themes.json`, 'utf8');
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

  it('pins fireproof and derives its 1-unit neighbor', () => {
    expect(themeTokens(normalizeSeeds({ bg: '#1c1b1a', fg: 'dad8ce', accent: '#CF6A4C' }))).toEqual(
      FIREPROOF,
    );
    const near = themeTokens(normalizeSeeds({ bg: '#1C1B1B', fg: '#DAD8CE', accent: '#CF6A4C' }));
    expect(near.accent_1).not.toBe(FIREPROOF.accent_1);
    expect(deriveTheme({ ...PRESETS.fireproof, ...FIREPROOF })).toEqual(FIREPROOF);
  });

  it('rejects missing seeds and unknown tokens', () => {
    expect(() => deriveTheme({ bg: '#000000', fg: '#FFFFFF' } as Seeds)).toThrow(/accent/);
    expect(() => deriveTheme({ ...PRESETS.nord, shadow: '#000000' } as Seeds)).toThrow(/shadow/);
  });
});

describe('theme tokens (e)', () => {
  const fixture = JSON.parse(readFileSync(`${FIXTURES}theme-tokens.json`, 'utf8')) as {
    valid: { spec: string | null; seeds: Seeds; token: string; cli_only: boolean }[];
    invalid: string[];
  };

  it.each(fixture.valid)('valid $spec', ({ spec, seeds, token, cli_only }) => {
    if (cli_only) {
      expect(parseToken(spec)).toBeNull();
    } else {
      expect(parseToken(spec)).toEqual(seeds);
    }
    expect(tokenOf(seeds)).toBe(token);
  });

  it.each(fixture.invalid)('invalid %s', (spec) => {
    expect(parseToken(spec)).toBeNull();
  });

  it('canonicalizes to the preset name or lowercase hex', () => {
    expect(tokenOf(normalizeSeeds({ bg: '1c1b1a', fg: '#DAD8CE', accent: 'cf6a4c' }))).toBe(
      'fireproof',
    );
    expect(tokenOf(normalizeSeeds({ bg: '#fff', fg: '#000', accent: '#F80' }))).toBe(
      'ffffff-000000-ff8800',
    );
    expect(presetOf(normalizeSeeds({ bg: '#2e3440', fg: '#eceff4', accent: '#88c0d0' }))).toBe(
      'nord',
    );
    expect(
      presetOf(normalizeSeeds({ bg: '#2e3441', fg: '#eceff4', accent: '#88c0d0' })),
    ).toBeNull();
    expect(normalizeSeed(' #aBc ')).toBe('#AABBCC');
    expect(normalizeSeed('#abcd')).toBeNull();
    expect(() => normalizeSeeds({ bg: 'nope', fg: '#000', accent: '#000' })).toThrow(/bg/);
  });

  it('never resolves a name inherited from Object.prototype', () => {
    expect(parseToken('constructor')).toBeNull();
    expect(parseToken('__proto__')).toBeNull();
  });
});

/** Custom properties of the first `selector {` block in `css`, comments removed. */
function block(css: string, selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  expect(start, selector).toBeGreaterThanOrEqual(0);
  const body = css.slice(start, css.indexOf('}', start));
  return Object.fromEntries(
    [...body.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
  );
}

function resolveVars(props: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  const value = (v: string): string => {
    const ref = /^var\((--[\w-]+)\)$/.exec(v);
    return ref ? value(props[ref[1]]) : v;
  };
  for (const [k, v] of Object.entries(props)) out[k] = value(v);
  return out;
}

describe('token order', () => {
  it('TOKENS follows walldye._theme.TOKENS', () => {
    const py = readFileSync(`${ROOT}walldye/_theme.py`, 'utf8');
    const tuple = /^TOKENS = \(([^)]*)\)/m.exec(py);
    expect(tuple).not.toBeNull();
    expect([...tuple![1].matchAll(/"(\w+)"/g)].map((m) => m[1])).toEqual([...TOKENS]);
  });
});

describe('site CSS', () => {
  const css = readFileSync(`${ROOT}src/styles/site.css`, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const root = block(css, ':root');
  const light = {
    ...root,
    ...block(css, ':root:not([data-regime])'),
    ...block(css, '[data-regime="light"]'),
  };

  it('fireproof reproduces the pinned :root block of site.css', () => {
    const want = resolveVars(root);
    const got = cssVars(PRESETS.fireproof);
    expect(Object.keys(got).sort()).toEqual(Object.keys(want).sort());
    expect(got).toEqual(want);
  });

  it('flexoki-light reproduces the light block of site.css', () => {
    expect(cssVars(PRESETS['flexoki-light'])).toEqual(resolveVars(light));
  });

  it('matches the contrast figures in docs/site.md', () => {
    const ratio = (a: string, b: string) => contrast(a, b).toFixed(2);
    const f = cssVars(PRESETS.fireproof);
    expect(ratio(f['--text'], f['--bg'])).toBe('12.03');
    expect(ratio(f['--link'], f['--bg'])).toBe('4.77');
    expect(ratio(f['--control'], f['--bg'])).toBe('3.03');
    expect(ratio(FIREPROOF.accent, f['--bg-alt'])).toBe('4.13');
    expect(ratio(f['--shiki-token-keyword'], f['--bg-alt'])).toBe('4.53');
    expect(ratio(f['--shiki-token-string'], f['--bg-alt'])).toBe('5.70');
    expect(ratio(f['--shiki-token-comment'], f['--bg-alt'])).toBe('7.26');
    const l = cssVars(PRESETS['flexoki-light']);
    expect(ratio(l['--text-2'], l['--bg'])).toBe('10.90');
    expect(ratio(l['--control'], l['--bg'])).toBe('3.54');
    expect(ratio(l['--shiki-token-keyword'], l['--bg-alt'])).toBe('4.52');
  });
});

describe('contrast guard (d)', () => {
  const themes: Seeds[] = [...Object.values(PRESETS), ...randomSeeds(1000)];

  it('holds for every guarded role over the presets and 1000 random triples', () => {
    const failures: string[] = [];
    for (const seeds of themes) {
      const vars = cssVars(seeds);
      const t = themeTokens(seeds);
      for (const [prop, token, surface, min] of GUARDED) {
        const got = vars[prop];
        if (contrast(got, t[surface]) < min)
          failures.push(`${tokenOf(seeds)} ${prop} ${got} on ${surface}`);
        if (got !== t[token] && contrast(t[token], t[surface]) >= min)
          failures.push(`${tokenOf(seeds)} ${prop} nudged needlessly`);
      }
    }
    expect(failures).toEqual([]);
  });

  it('nudges no further than needed, towards the pole that contrasts more', () => {
    const next = rng(7);
    let nudged = 0;
    for (const seeds of themes.slice(0, 300)) {
      const t = themeTokens(seeds);
      for (const surface of [t.bg, t.bg_alt]) {
        const c = t.accent;
        const min = next() < 0.5 ? 3 : 4.5;
        const got = guard(c, surface, min);
        if (got === c) continue;
        nudged++;
        const pole =
          contrast('#000000', surface) >= contrast('#FFFFFF', surface) ? '#000000' : '#FFFFFF';
        // The first passing step of a 1/512 scan bounds how far the smallest t can have moved.
        let scan = pole;
        for (let i = 1; i <= 512; i++) {
          const m = mix(c, pole, i / 512);
          if (contrast(m, surface) >= min) {
            scan = m;
            break;
          }
        }
        const moved = Math.abs(luminance(got) - luminance(c));
        expect(moved).toBeLessThanOrEqual(Math.abs(luminance(scan) - luminance(c)) + 1e-12);
        expect(
          (luminance(got) - luminance(c)) * (luminance(pole) - luminance(c)),
        ).toBeGreaterThanOrEqual(0);
      }
    }
    expect(nudged).toBeGreaterThan(50);
  });

  it('keeps a disabled label at 4.5:1, faded only as far as that allows', () => {
    const failures: string[] = [];
    for (const seeds of themes) {
      const v = cssVars(seeds);
      const bg = themeTokens(seeds).bg;
      const faded = mix(v['--text-2'], bg, DIM);
      if (contrast(v['--text-dim'], bg) < 4.5)
        failures.push(`${tokenOf(seeds)} --text-dim ${v['--text-dim']}`);
      if (v['--text-dim'] !== faded && contrast(faded, bg) >= 4.5)
        failures.push(`${tokenOf(seeds)} --text-dim nudged needlessly`);
    }
    expect(failures).toEqual([]);
    // solarized-light's guarded --text-2 has no room to fade: at 0.75 opacity it was 2.9:1.
    const sol = cssVars(PRESETS['solarized-light']);
    expect(contrast(mix(sol['--text-2'], sol['--bg'], DIM), sol['--bg'])).toBeLessThan(3);
  });

  it('switches the rules one gray step up in the light regime', () => {
    const dark = cssVars(PRESETS.nord);
    const t = themeTokens(PRESETS.nord);
    expect([dark['--rule'], dark['--rule-strong']]).toEqual([t.ui_alt, t.ui_hi]);
    const light = cssVars(PRESETS['solarized-light']);
    const l = themeTokens(PRESETS['solarized-light']);
    expect([light['--rule'], light['--rule-strong']]).toEqual([l.ui, l.ui_alt]);
    expect(light['--seed-bg']).toBe('#FDF6E3');
  });
});
