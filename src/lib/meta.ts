/**
 * Rules over a parsed meta.yaml shared by CI and the content schema: the licence default and draft
 * flag (ports of walldye/tools/lint.py license_of and common.is_draft) and the copy lint
 * (design.md, Copy rules; SPEC.md, Voice).
 */

export const DEFAULT_LICENSE = 'CC0-1.0';
export const FAN_WORK = 'LicenseRef-fan-work';
export const MAX_DESCRIPTION_WORDS = 30;
export const MAX_DESCRIPTION_SENTENCES = 2;

type Meta = Record<string, unknown>;

/** Whether `meta` marks its piece a draft: only `draft: true` does. */
export function isDraft(meta: Meta): boolean {
  return meta.draft === true;
}

/** The folder's licence: `license:`, else DEFAULT_LICENSE for an AI-generated piece with no recreation source, else null. */
export function licenseOf(meta: Meta): unknown {
  if (meta.license) return meta.license;
  const sources = Array.isArray(meta.sources) ? meta.sources : [];
  const recreation = sources.some((s) => typeof s === 'object' && s !== null && (s as Meta).kind === 'recreation');
  return meta.ai_generated === true && !recreation ? DEFAULT_LICENSE : null;
}

/** walldye/tools/lint.py COLOUR_WORDS: hues and named shades that copy never names. */
export const COLOUR_WORDS: ReadonlySet<string> = new Set([
  'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'violet', 'pink', 'brown', 'black',
  'white', 'grey', 'gray', 'cyan', 'magenta', 'teal', 'turquoise', 'indigo', 'crimson',
  'scarlet', 'maroon', 'amber', 'golden', 'beige', 'cream', 'ivory', 'terracotta', 'ochre',
  'umber', 'sepia', 'navy', 'lavender', 'lilac', 'mauve', 'azure', 'cobalt', 'vermilion',
  'burgundy', 'charcoal', 'khaki', 'sienna', 'cerulean', 'ultramarine', 'chartreuse', 'fuchsia',
]);

/** Colour words in `text`, lowercased and sorted; ALL-CAPS words (token names like ORANGE_DARK) are not prose. */
export function colourWords(text: string): string[] {
  const found = new Set<string>();
  for (const [w] of text.matchAll(/(?<![\p{L}\p{N}_])[A-Za-z]+(?![\p{L}\p{N}_])/gu)) {
    const upper = w === w.toUpperCase();
    if (COLOUR_WORDS.has(w.toLowerCase()) && !upper) found.add(w.toLowerCase());
  }
  return [...found].sort();
}

/** Phrases visible copy never uses, each with the reason shown by lintCopy. Matched case-insensitively as whole words. */
export const BANNED: readonly (readonly [RegExp, string])[] = [
  [
    /\b(stunning|mesmeri[sz]ing|elegant|timeless|beautiful(ly)?|breathtaking|captivating|gorgeous|exquisite|hypnotic|vibrant|evocative|sublime|majestic|iconic|dazzling|striking)\b/i,
    'evaluative adjective',
  ],
  [/\b(delve[sd]?|delving|tapestry|testament|quietly|seamless(ly)?|serves as|stands as)\b/i, 'stock phrase'],
  [
    /\b(regimes?|seeds?|tokens?|native|hand-tuned|light-ready|presets?|slots?|templates?|derived|guards?|has script|AI-generated|generator lost|appendix)\b/i,
    'internal term',
  ],
  [/\b(CC0(-1\.0)?|GPL(-[\w.-]+)?|SPDX|OFL|LicenseRef-[\w.-]*)(?![\w-])/i, 'licence identifier'],
  [/\bRGB units?\b|\b\d+(\.\d+)?:1\b|\b\d+\s?px\b/i, 'machinery number'],
  [/\bthe accent\b|\baccent colou?r\b|\b(bg|fg)(_alt)?\b/i, 'theme role as a noun'],
];

function words(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

/** Sentences in `text`: a sentence ends at . ! or ? before whitespace and a capital, or at the end, so "Fig. 1" does not end one. */
export function sentences(text: string): number {
  const t = text.trim();
  if (!t) return 0;
  const ends = t.match(/[.!?]+(?=\s+[\p{Lu}"“‘(]|$)/gu)?.length ?? 0;
  return /[.!?]$/.test(t) ? ends : ends + 1;
}

/**
 * Copy problems in the title, description and notes of `meta`, each as "<field>: <problem>": colour
 * words and BANNED phrases in any of them; a description over MAX_DESCRIPTION_WORDS words or
 * MAX_DESCRIPTION_SENTENCES sentences. [] when the copy follows the rules.
 */
export function lintCopy(meta: Meta): string[] {
  const out: string[] = [];
  for (const field of ['title', 'description', 'notes'] as const) {
    const text = meta[field] ? String(meta[field]) : '';
    if (!text) continue;
    const colours = colourWords(text);
    if (colours.length) out.push(`${field}: colour words ${colours.join(', ')}`);
    for (const [re, why] of BANNED) {
      const m = re.exec(text);
      if (m) out.push(`${field}: ${why} "${m[0]}"`);
    }
    if (field === 'description') {
      const n = words(text);
      if (n > MAX_DESCRIPTION_WORDS) out.push(`description: ${n} words, over ${MAX_DESCRIPTION_WORDS}`);
      const s = sentences(text);
      if (s > MAX_DESCRIPTION_SENTENCES) out.push(`description: ${s} sentences, over ${MAX_DESCRIPTION_SENTENCES}`);
    }
  }
  return out;
}
