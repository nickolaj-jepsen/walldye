/**
 * Seeds from text a visitor pastes into the picker: a theme token, three colors, or a terminal or
 * base16 theme file (kitty, Ghostty, Alacritty TOML or YAML, foot, WezTerm, Windows Terminal JSON,
 * Xresources, base16 and base24 YAML). Pure functions, no DOM.
 */
import { contrast, type Hex, hexToRgb, normalizeSeed, parseToken, type Seeds } from './theme';

/** Sections and keys whose colors are not the theme's own ground, text or normal ANSI colors. */
const SKIP =
  /bright|dim|selection|cursor|search|hint|footer|indicator|vi_mode|tab|url|bell|inactive/i;

/** ANSI color names as the files spell them, to their index. */
const ANSI: Record<string, number> = {
  black: 0,
  red: 1,
  green: 2,
  yellow: 3,
  blue: 4,
  magenta: 5,
  purple: 5,
  cyan: 6,
  white: 7,
};

/** base16's accent slots, base08 (red) to base0E (purple). */
const BASE16_ACCENTS = ['base08', 'base09', 'base0a', 'base0b', 'base0c', 'base0d', 'base0e'];

/** An accent must reach this contrast on the ground to be picked over a more colorful one. */
const ACCENT_CONTRAST = 3;

const ENTRY = /^\s*["']?([\w*.-]+)["']?\s*(?:[:=]\s*|\s+)["']?#?([0-9a-fA-F]{6})(?![0-9a-fA-F])/;
const PALETTE = /^\s*palette\s*=\s*(\d+)\s*=\s*#?([0-9a-fA-F]{6})(?![0-9a-fA-F])/;
const ARRAY = /^\s*["']?ansi["']?\s*[:=]\s*\[/;
const SECTION = /^\s*\[+([^\]]+)\]+\s*$/;
const PARENT = /^(\s*)["']?([\w.-]+)["']?\s*:\s*$/;

/** The name an entry's key goes by: `colorN` for ANSI colors, else the key's last segment, lowercase. */
function keyName(key: string): string {
  const last = (key.split(/[*.]/).pop() ?? '').toLowerCase();
  if (Object.hasOwn(ANSI, last)) return `color${ANSI[last]}`;
  const regular = /^regular(\d)$/.exec(last);
  return regular ? `color${regular[1]}` : last;
}

/** Every color the text names, by keyName(); the first of a name wins. Hex values without a key are ignored. */
export function namedColors(text: string): Map<string, Hex> {
  const out = new Map<string, Hex>();
  const put = (name: string, hex: string) => {
    const v = normalizeSeed(hex);
    if (v && !out.has(name)) out.set(name, v);
  };
  let section = '';
  // YAML parents of the current line, by indent.
  const parents: { indent: number; key: string }[] = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const indent = /^\s*/.exec(line)?.[0].length ?? 0;
    while (parents.length && parents[parents.length - 1].indent >= indent) parents.pop();
    const head = SECTION.exec(line);
    if (head) {
      section = head[1].trim();
      parents.length = 0;
      continue;
    }
    const parent = PARENT.exec(line);
    if (parent) {
      parents.push({ indent, key: parent[2] });
      continue;
    }
    const where = [section, ...parents.map((p) => p.key)].join('.');
    if (SKIP.test(where)) continue;
    const palette = PALETTE.exec(line);
    if (palette) {
      put(`color${palette[1]}`, palette[2]);
      continue;
    }
    if (ARRAY.test(line)) {
      // A WezTerm `ansi = [...]` list, on one line or several.
      let body = line.slice(line.indexOf('[') + 1);
      while (!body.includes(']') && i + 1 < lines.length) body += lines[++i];
      const hexes = body.slice(0, body.indexOf(']') + 1).match(/#?[0-9a-fA-F]{6}(?![0-9a-fA-F])/g);
      hexes?.forEach((h, n) => {
        put(`color${n}`, h);
      });
      continue;
    }
    const entry = ENTRY.exec(line);
    if (entry && !SKIP.test(entry[1])) put(keyName(entry[1]), entry[2]);
  }
  return out;
}

/** How colorful `c` is: its largest channel minus its smallest, 0..255. */
function chroma(c: string): number {
  const rgb = hexToRgb(c);
  return Math.max(...rgb) - Math.min(...rgb);
}

/**
 * The accent among `candidates`: the most colorful one reaching ACCENT_CONTRAST on `bg`, else the
 * one with the most contrast; the first on a tie. Undefined when there are none.
 */
export function pickAccent(candidates: readonly Hex[], bg: Hex): Hex | undefined {
  const strong = candidates.filter((c) => contrast(c, bg) >= ACCENT_CONTRAST);
  const pool = strong.length ? strong : candidates;
  const score = strong.length ? chroma : (c: string) => contrast(c, bg);
  let best: Hex | undefined;
  for (const c of pool) if (best === undefined || score(c) > score(best)) best = c;
  return best;
}

/**
 * Seeds from pasted text: a theme token, three hex colors separated by commas, spaces or dashes, or
 * a theme file. A file gives its background and foreground (base00 and base05 in base16), and its
 * `accent` when it names one, else pickAccent() over its normal ANSI colors 1 to 6 or base08 to
 * base0E. Null when the text holds none of these.
 */
export function seedsFromText(text: string): Seeds | null {
  const t = text.trim();
  const token = parseToken(t);
  if (token) return token;
  const parts = t.split(/[\s,-]+/).filter(Boolean);
  if (parts.length === 3) {
    const [bg, fg, accent] = parts.map(normalizeSeed);
    if (bg && fg && accent) return { bg, fg, accent };
  }
  const named = namedColors(t);
  const bg = named.get('background') ?? named.get('bg') ?? named.get('base00');
  const fg = named.get('foreground') ?? named.get('fg') ?? named.get('base05');
  if (!bg || !fg) return null;
  const ansi = [1, 2, 3, 4, 5, 6].map((n) => named.get(`color${n}`));
  const base16 = BASE16_ACCENTS.map((k) => named.get(k));
  const candidates = [...ansi, ...base16].filter((c): c is Hex => c !== undefined);
  const accent = named.get('accent') ?? pickAccent(candidates, bg);
  return accent ? { bg, fg, accent } : null;
}
