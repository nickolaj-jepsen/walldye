/**
 * Theme model, ported from walldye/_theme.py: three seeds (bg, fg, accent) derive the 21 tokens,
 * and the site's CSS roles are those tokens passed through the contrast guard. Pure functions, no DOM.
 *
 * Colours are `#RRGGBB` strings; every function returns uppercase hex like the Python side.
 */

export type Seed = 'bg' | 'fg' | 'accent';
export type Seeds = Record<Seed, string>;
export type Regime = 'dark' | 'light';

export const SEEDS: readonly Seed[] = ['bg', 'fg', 'accent'];
export const TOKENS = [
  'black', 'bg_deep', 'bg', 'bg_alt', 'ui', 'ui_alt', 'ui_hi', 'muted', 'fg_alt', 'fg',
  'accent_hi', 'accent', 'accent_1', 'accent_2', 'accent_3', 'accent_4',
  'accent_5', 'accent_6', 'accent_7', 'accent_8', 'orange_dark',
] as const;
export type Token = (typeof TOKENS)[number];
export type Tokens = Record<Token, string>;

/** walldye.GREYS order: black to muted. */
export const GREYS: readonly Token[] = ['black', 'bg_deep', 'bg', 'bg_alt', 'ui', 'ui_alt', 'ui_hi', 'muted'];
/** walldye.ACCENTS order: bg-ward to accent, the ramp most designs step through. */
export const ACCENTS: readonly Token[] = [
  'accent_8', 'accent_7', 'accent_6', 'accent_5', 'accent_4', 'accent_3', 'accent_2', 'accent_1', 'accent',
];

const GREY_T: readonly (readonly [Token, number])[] = [
  ['bg_alt', 0.063], ['ui', 0.126], ['ui_alt', 0.189], ['ui_hi', 0.31], ['muted', 0.563], ['fg_alt', 0.816],
];
const ACCENT_T: readonly (readonly [Token, number])[] = [
  ['accent_1', 0.17], ['accent_2', 0.26], ['accent_3', 0.5], ['accent_4', 0.56],
  ['accent_5', 0.68], ['accent_6', 0.8], ['accent_7', 0.9], ['accent_8', 0.955],
];
const WIDENED: ReadonlySet<Token> = new Set(['bg_alt', 'ui', 'ui_alt', 'ui_hi']);

/** fireproof's hand-pinned tokens; its exact seeds resolve to this table, never to deriveTheme. */
export const FIREPROOF: Readonly<Tokens> = {
  black: '#100F0F', bg_deep: '#181716', bg: '#1C1B1A', bg_alt: '#282726',
  ui: '#343331', ui_alt: '#403E3C', ui_hi: '#575653', muted: '#878580',
  fg_alt: '#B7B5AC', fg: '#DAD8CE',
  accent_hi: '#E08A6E', accent: '#CF6A4C', accent_1: '#B14D2F', accent_2: '#A1462B',
  accent_3: '#71311E', accent_4: '#6B3528', accent_5: '#55291F', accent_6: '#40211B',
  accent_7: '#2E1C19', accent_8: '#241B19', orange_dark: '#BC5215',
};

/** Preset seeds in walldye.PRESETS order (the picker's order; the first match names a theme). */
export const PRESETS: Readonly<Record<string, Readonly<Seeds>>> = {
  fireproof: { bg: FIREPROOF.bg, fg: FIREPROOF.fg, accent: FIREPROOF.accent },
  'flexoki-light': { bg: '#FFFCF0', fg: '#100F0F', accent: '#BC5215' },
  'gruvbox-dark': { bg: '#282828', fg: '#EBDBB2', accent: '#FE8019' },
  nord: { bg: '#2E3440', fg: '#ECEFF4', accent: '#88C0D0' },
  'catppuccin-mocha': { bg: '#1E1E2E', fg: '#CDD6F4', accent: '#CBA6F7' },
  'tokyo-night': { bg: '#1A1B26', fg: '#C0CAF5', accent: '#7AA2F7' },
  'rose-pine': { bg: '#191724', fg: '#E0DEF4', accent: '#EBBCBA' },
  'everforest-dark': { bg: '#2D353B', fg: '#D3C6AA', accent: '#A7C080' },
  'ayu-dark': { bg: '#0B0E14', fg: '#BFBDB6', accent: '#E6B450' },
  dracula: { bg: '#282A36', fg: '#F8F8F2', accent: '#FF79C6' },
  'solarized-light': { bg: '#FDF6E3', fg: '#586E75', accent: '#CB4B16' },
};
export const DEFAULT_THEME = 'fireproof';

const SEED_RE = /^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** Python's round(): nearest integer, ties to even. */
export function roundHalfEven(x: number): number {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

/** [r, g, b] of a 3- or 6-digit hex colour, leading `#`s optional. */
export function hexToRgb(c: string): [number, number, number] {
  let h = c.replace(/^#+/, '');
  if (h.length === 3) h = h.replace(/./g, '$&$&');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** Uppercase #RRGGBB; channels are rounded half to even, then clamped to 0..255. */
export function rgbToHex(r: number, g: number, b: number): string {
  let out = '#';
  for (const v of [r, g, b]) out += Math.max(0, Math.min(255, roundHalfEven(v))).toString(16).padStart(2, '0');
  return out.toUpperCase();
}

/** Linear RGB blend from `a` (t=0) to `b` (t=1). */
export function mix(a: string, b: string, t: number): string {
  const [ra, ga, ba] = hexToRgb(a);
  const [rb, gb, bb] = hexToRgb(b);
  return rgbToHex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t);
}

function lin(v: number): number {
  v /= 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

/** WCAG relative luminance of a hex colour, 0..1. */
export function luminance(c: string): number {
  const [r, g, b] = hexToRgb(c);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG contrast ratio of two colours, 1..21. */
export function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** True for the light regime: bg strictly brighter than fg (equal luminance is dark). */
export function isLight(bg: string, fg: string): boolean {
  return luminance(bg) > luminance(fg);
}

/**
 * All 21 tokens from `seeds` (bg, fg, accent), with any other token in `seeds` as an override,
 * uppercased but not otherwise normalised. Throws on a missing seed or an unknown token name.
 */
export function deriveTheme(seeds: Seeds & Partial<Tokens>): Tokens {
  const missing = SEEDS.filter((k) => !(k in seeds));
  if (missing.length) throw new Error(`theme needs ${missing.sort().join(', ')}`);
  const unknown = Object.keys(seeds).filter((k) => !(TOKENS as readonly string[]).includes(k));
  if (unknown.length) throw new Error(`unknown theme tokens: ${unknown.sort().join(', ')}`);
  const { bg, fg, accent } = seeds;
  const dark = !isLight(bg, fg);
  const beyond = dark ? '#000000' : '#FFFFFF';
  // Thin grey structure reads fainter on paper than on a dark ground; widen the low steps.
  const boost = dark ? 1.0 : 1.6;
  const t: Partial<Record<Token, string>> = {
    bg_deep: mix(bg, beyond, 0.15),
    black: mix(bg, beyond, 0.43),
    accent_hi: mix(accent, fg, 0.28),
  };
  for (const [k, v] of GREY_T) t[k] = mix(bg, fg, WIDENED.has(k) ? Math.min(v * boost, 0.5) : v);
  for (const [k, v] of ACCENT_T) t[k] = mix(accent, bg, v);
  t.orange_dark = t.accent_1;
  Object.assign(t, seeds);
  const out = {} as Tokens;
  for (const k of TOKENS) out[k] = (t[k] as string).toUpperCase();
  return out;
}

/** `c` (3 or 6 hex digits, optional `#`, any case, surrounding whitespace ignored) as uppercase #RRGGBB, or null. */
export function normaliseSeed(c: string): string | null {
  const m = SEED_RE.exec(c.trim());
  if (!m) return null;
  const h = m[1];
  return '#' + (h.length === 6 ? h : h.replace(/./g, '$&$&')).toUpperCase();
}

/** `seeds` with each seed normalised; throws naming the first invalid one. */
export function normaliseSeeds(seeds: Seeds): Seeds {
  const out = {} as Seeds;
  for (const k of SEEDS) {
    const v = normaliseSeed(seeds[k]);
    if (v === null) throw new Error(`bad ${k} colour ${JSON.stringify(seeds[k])}`);
    out[k] = v;
  }
  return out;
}

function sameSeeds(a: Seeds, b: Seeds): boolean {
  return a.bg === b.bg && a.fg === b.fg && a.accent === b.accent;
}

/**
 * Seeds (uppercase #RRGGBB) for a site theme token, or null when `spec` is not one.
 *
 * The site grammar is a preset name (exact case) or `bg-fg-accent`, each seed 3 or 6 hex digits
 * with an optional `#`, any case; whitespace around the token and around each seed is ignored.
 * The CLI-only forms (`bg,fg,accent`, `bg=..,fg=..,accent=..`, empty for the default) are rejected.
 */
export function parseToken(spec: string | null | undefined): Seeds | null {
  if (typeof spec !== 'string') return null;
  const s = spec.trim();
  if (Object.hasOwn(PRESETS, s)) return { ...PRESETS[s] };
  const parts = s.split('-');
  if (parts.length !== 3) return null;
  const [bg, fg, accent] = parts.map(normaliseSeed);
  return bg && fg && accent ? { bg, fg, accent } : null;
}

/** The preset whose seeds equal `seeds` (normalised first), or null. */
export function presetOf(seeds: Seeds): string | null {
  const s = normaliseSeeds(seeds);
  for (const name in PRESETS) if (sameSeeds(s, PRESETS[name])) return name;
  return null;
}

/** Canonical token for `seeds`: the preset name when they equal a preset's, else lowercase `bg-fg-accent` without `#`. */
export function tokenOf(seeds: Seeds): string {
  const s = normaliseSeeds(seeds);
  return presetOf(s) ?? SEEDS.map((k) => s[k].slice(1).toLowerCase()).join('-');
}

/** The regime of `seeds`. */
export function regimeOf(seeds: Seeds): Regime {
  return isLight(seeds.bg, seeds.fg) ? 'light' : 'dark';
}

/** All 21 tokens: the pinned FIREPROOF table for fireproof's exact seeds, deriveTheme otherwise. Seeds are normalised first. */
export function themeTokens(seeds: Seeds): Tokens {
  const s = normaliseSeeds(seeds);
  return sameSeeds(s, PRESETS.fireproof) ? { ...FIREPROOF } : deriveTheme(s);
}

/**
 * `c` unchanged when it reaches `min` contrast on `surface`, else `mix(c, pole, t)` for the smallest t
 * that does, found by binary search; the pole is whichever of #000000/#FFFFFF contrasts more with
 * `surface` (black on a tie). Every surface has a pole of at least 4.58:1, so any `min` up to that is met.
 */
export function guard(c: string, surface: string, min: number): string {
  if (contrast(c, surface) >= min) return c;
  const pole = contrast('#000000', surface) >= contrast('#FFFFFF', surface) ? '#000000' : '#FFFFFF';
  let lo = 0;
  let hi = 1;
  for (let i = 0; i < 32; i++) {
    const t = (lo + hi) / 2;
    if (contrast(mix(c, pole, t), surface) >= min) hi = t;
    else lo = t;
  }
  return mix(c, pole, hi);
}

/** A contrast-guarded CSS role: [custom property, token, surface token, minimum ratio]. */
export type GuardedRole = readonly [prop: string, token: Token, surface: 'bg' | 'bg_alt', min: number];

/** Every guarded role of site.css (SPEC.md, Tokens): text 4.5:1, controls and focus 3:1, listing tokens against bg_alt. */
export const GUARDED: readonly GuardedRole[] = [
  ['--text', 'fg', 'bg', 4.5],
  ['--text-2', 'fg_alt', 'bg', 4.5],
  ['--link', 'accent', 'bg', 4.5],
  ['--control', 'ui_hi', 'bg', 3],
  ['--link-line', 'ui_hi', 'bg', 3],
  ['--focus', 'accent', 'bg', 3],
  ['--shiki-foreground', 'fg', 'bg_alt', 4.5],
  ['--shiki-token-keyword', 'accent', 'bg_alt', 4.5],
  ['--shiki-token-string', 'accent_hi', 'bg_alt', 4.5],
  ['--shiki-token-string-expression', 'accent_hi', 'bg_alt', 4.5],
  ['--shiki-token-constant', 'fg', 'bg_alt', 4.5],
  ['--shiki-token-comment', 'fg_alt', 'bg_alt', 4.5],
  ['--shiki-token-parameter', 'fg', 'bg_alt', 4.5],
  ['--shiki-token-punctuation', 'fg_alt', 'bg_alt', 4.5],
  ['--shiki-token-function', 'fg', 'bg_alt', 4.5],
  ['--shiki-token-link', 'fg', 'bg_alt', 4.5],
  ['--listing-gutter', 'fg_alt', 'bg_alt', 4.5],
];

/** How far a disabled control's label fades from `--text-2` towards bg before the guard (SPEC 6.4's 0.75 opacity). */
export const DIM = 0.25;

/**
 * Every colour custom property site.css reads, for `seeds` (normalised first; throws on an invalid seed):
 * the raw seeds, the tokens the stylesheet names, the unguarded roles (leader, rules, plate edge,
 * listing ground; rules step up one grey in the light regime), the GUARDED roles, and `--text-dim`,
 * the label of a disabled control: `--text-2` faded DIM towards bg, guarded back to 4.5:1 on bg.
 */
export function cssVars(seeds: Seeds): Record<string, string> {
  const s = normaliseSeeds(seeds);
  const t = themeTokens(s);
  const light = isLight(s.bg, s.fg);
  const vars: Record<string, string> = {
    '--seed-bg': s.bg,
    '--seed-fg': s.fg,
    '--seed-accent': s.accent,
    '--bg': t.bg,
    '--bg-alt': t.bg_alt,
    '--ui': t.ui,
    '--ui-alt': t.ui_alt,
    '--ui-hi': t.ui_hi,
    '--muted': t.muted,
    '--fg-alt': t.fg_alt,
    '--fg': t.fg,
    '--accent': t.accent,
    '--accent-hi': t.accent_hi,
    '--leader': t.muted,
    '--rule': light ? t.ui : t.ui_alt,
    '--rule-strong': light ? t.ui_alt : t.ui_hi,
    '--plate-edge': t.ui,
    '--shiki-background': t.bg_alt,
  };
  const memo = new Map<string, string>();
  for (const [prop, token, surface, min] of GUARDED) {
    const key = `${token} ${surface} ${min}`;
    let v = memo.get(key);
    if (v === undefined) memo.set(key, (v = guard(t[token], t[surface], min)));
    vars[prop] = v;
  }
  vars['--text-dim'] = guard(mix(vars['--text-2'], t.bg, DIM), t.bg, 4.5);
  return vars;
}
