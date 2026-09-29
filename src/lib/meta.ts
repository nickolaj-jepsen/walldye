/**
 * Rules over a parsed meta.yaml shared by CI and the content schema: the licence default and draft
 * flag (ports of walldye/tools/lint.py license_of and common.is_draft), the `variants:` mapping
 * and the copy lint.
 */

import { z } from 'astro/zod';
import { DEFAULT_VARIANT } from './content';

export const DEFAULT_LICENSE = 'CC0-1.0';
export const FAN_WORK = 'LicenseRef-fan-work';
export const MAX_DESCRIPTION_WORDS = 30;
export const MAX_DESCRIPTION_SENTENCES = 2;
/** Named variants per design, so at most 5 versions with the default. */
export const MAX_VARIANTS = 4;
export const MAX_LABEL_WORDS = 4;
const MAX_VARIANT_NAME = 24;
/** A variant name: lowercase words joined by single hyphens, so `<slug>--<name>` splits back. */
export const VARIANT_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

type Meta = Record<string, unknown>;

/** Whether `meta` marks its piece a draft: only `draft: true` does. */
export function isDraft(meta: Meta): boolean {
  return meta.draft === true;
}

const variantEntry = z
  .object({
    /** Names the version in the detail page's switcher. */
    label: z.string().trim().min(1),
    /** Replaces the piece's description while this version is shown; named variants only. */
    description: z.string().trim().min(1).optional(),
    /** Built but hidden from the production site; named variants only. */
    draft: z.boolean().optional(),
  })
  .strict();

/**
 * meta.yaml `variants:`: `default` plus every named variant design.py declares, each with a label of
 * at most MAX_LABEL_WORDS words, unique within the piece. At most MAX_VARIANTS named variants;
 * `description` and `draft` belong to named variants only. Whether the names match design.py is
 * `walldye check`'s to say.
 */
export const variantsMeta = z.record(z.string(), variantEntry).superRefine((vs, ctx) => {
  const issue = (message: string, path: string[] = []) =>
    ctx.addIssue({ code: 'custom', message, path });
  const names = Object.keys(vs).filter((k) => k !== DEFAULT_VARIANT);
  const unnamed = vs[DEFAULT_VARIANT];
  if (!unnamed)
    issue('needs a default entry, the label of the version design.py draws without a variant');
  if (!names.length) issue('lists no named variants; leave variants: out');
  if (names.length > MAX_VARIANTS)
    issue(`at most ${MAX_VARIANTS} named variants, got ${names.length}`);
  for (const name of names) {
    if (!VARIANT_NAME.test(name) || name.length > MAX_VARIANT_NAME) {
      issue(
        `${name} is not a variant name: lowercase words joined by single hyphens, at most ${MAX_VARIANT_NAME} characters`,
        [name],
      );
    }
  }
  if (unnamed?.description !== undefined)
    issue('the default version shows the piece description', [DEFAULT_VARIANT, 'description']);
  if (unnamed?.draft !== undefined)
    issue('the default version is a draft only with the piece', [DEFAULT_VARIANT, 'draft']);
  const seen = new Map<string, string>();
  for (const [name, v] of Object.entries(vs)) {
    const n = words(v.label);
    if (n > MAX_LABEL_WORDS)
      issue(`label has ${n} words, over ${MAX_LABEL_WORDS}`, [name, 'label']);
    const key = v.label.toLowerCase();
    const other = seen.get(key);
    if (other !== undefined) issue(`label repeats the label of ${other}`, [name, 'label']);
    else seen.set(key, name);
  }
});

export interface NamedVariant {
  name: string;
  label: unknown;
  description: unknown;
  draft: boolean;
}

const isMapping = (v: unknown): v is Meta =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/**
 * The named variants under meta.yaml `variants:`, in file order, read without validating them
 * (variantsMeta reports what is wrong) and leaving out entries that are not mappings, as
 * walldye/tools/common.py meta_variants does; [] when the key is absent or not a mapping.
 */
export function namedVariants(meta: Meta): NamedVariant[] {
  const vs = meta.variants;
  if (!isMapping(vs)) return [];
  return Object.entries(vs)
    .filter((e): e is [string, Meta] => e[0] !== DEFAULT_VARIANT && isMapping(e[1]))
    .map(([name, e]) => ({ name, label: e.label, description: e.description, draft: isDraft(e) }));
}

/**
 * The folder's licence: `license:`, else FAN_WORK when `franchise:` is set, else DEFAULT_LICENSE for a
 * piece a model made (`model:`) with no recreation source, else null.
 */
export function licenseOf(meta: Meta): unknown {
  if (meta.license) return meta.license;
  if ('franchise' in meta) return FAN_WORK;
  const sources = Array.isArray(meta.sources) ? meta.sources : [];
  const recreation = sources.some(
    (s) => typeof s === 'object' && s !== null && (s as Meta).kind === 'recreation',
  );
  return meta.model && !recreation ? DEFAULT_LICENSE : null;
}

/** walldye/tools/lint.py COLOUR_WORDS: hues and named shades that copy never names. */
export const COLOUR_WORDS: ReadonlySet<string> = new Set([
  'red',
  'orange',
  'yellow',
  'green',
  'blue',
  'purple',
  'violet',
  'pink',
  'brown',
  'black',
  'white',
  'grey',
  'gray',
  'cyan',
  'magenta',
  'teal',
  'turquoise',
  'indigo',
  'crimson',
  'scarlet',
  'maroon',
  'amber',
  'golden',
  'beige',
  'cream',
  'ivory',
  'terracotta',
  'ochre',
  'umber',
  'sepia',
  'navy',
  'lavender',
  'lilac',
  'mauve',
  'azure',
  'cobalt',
  'vermilion',
  'burgundy',
  'charcoal',
  'khaki',
  'sienna',
  'cerulean',
  'ultramarine',
  'chartreuse',
  'fuchsia',
]);

/**
 * Colour words in `text` as written, lowercased and sorted, plurals included ("greys" matches via "grey");
 * ALL-CAPS words (token names like ORANGE_DARK) are not prose.
 */
export function colourWords(text: string): string[] {
  const found = new Set<string>();
  for (const [w] of text.matchAll(/(?<![\p{L}\p{N}_])[A-Za-z]+(?![\p{L}\p{N}_])/gu)) {
    const lower = w.toLowerCase();
    const stems = [lower, lower.replace(/s$/, ''), lower.replace(/es$/, '')];
    if (w !== w.toUpperCase() && stems.some((t) => COLOUR_WORDS.has(t))) found.add(lower);
  }
  return [...found].sort();
}

/** Phrases visible copy never uses, each with the reason shown by lintCopy. Matched case-insensitively as whole words. */
export const BANNED: readonly (readonly [RegExp, string])[] = [
  [
    /\b(stunning|mesmeri[sz]ing|elegant|timeless|beautiful(ly)?|breathtaking|captivating|gorgeous|exquisite|hypnotic|vibrant|evocative|sublime|majestic|iconic|dazzling|striking)\b/i,
    'evaluative adjective',
  ],
  [
    /\b(delve[sd]?|delving|tapestry|testament|quietly|seamless(ly)?|serves as|stands as)\b/i,
    'stock phrase',
  ],
  [
    /\b(regimes?|seeds?|tokens?|native|hand-tuned|light-ready|presets?|variants?|params?|slots?|templates?|derived|guards?|has script|AI-generated|generator lost|appendix)\b/i,
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
 * Copy problems in the title, description and notes of `meta` and in each variant's label and
 * description, each as "<field>: <problem>" (a variant field as `variants.<name>.label`): colour words
 * and BANNED phrases in any of them; a description over MAX_DESCRIPTION_WORDS words or
 * MAX_DESCRIPTION_SENTENCES sentences. [] when the copy follows the rules.
 */
export function lintCopy(meta: Meta): string[] {
  const fields: [string, unknown, boolean][] = [
    ['title', meta.title, false],
    ['description', meta.description, true],
    ['notes', meta.notes, false],
  ];
  const vs = meta.variants;
  if (isMapping(vs)) {
    for (const [name, e] of Object.entries(vs)) {
      if (isMapping(e))
        fields.push(
          [`variants.${name}.label`, e.label, false],
          [`variants.${name}.description`, e.description, true],
        );
    }
  }
  const out: string[] = [];
  for (const [field, value, isDescription] of fields) {
    const text = value ? String(value) : '';
    if (!text) continue;
    const colours = colourWords(text);
    if (colours.length) out.push(`${field}: colour words ${colours.join(', ')}`);
    for (const [re, why] of BANNED) {
      const m = re.exec(text);
      if (m) out.push(`${field}: ${why} "${m[0]}"`);
    }
    if (isDescription) {
      const n = words(text);
      if (n > MAX_DESCRIPTION_WORDS)
        out.push(`${field}: ${n} words, over ${MAX_DESCRIPTION_WORDS}`);
      const s = sentences(text);
      if (s > MAX_DESCRIPTION_SENTENCES)
        out.push(`${field}: ${s} sentences, over ${MAX_DESCRIPTION_SENTENCES}`);
    }
  }
  return out;
}

/**
 * `text` with typewriter quotes turned into typographer's quotes, matching what the notes' Markdown
 * gets: an apostrophe inside or after a word becomes ’ (Baldur’s, players’), a quote opening a word
 * becomes ‘ or “, and a double quote after a word or punctuation becomes ”. Quotes after figures,
 * such as feet, inches and lignes (16½'''), stay as they are.
 */
export function smartQuotes(text: string): string {
  return text
    .replace(/(?<=[\p{L}\p{N}])'(?=\p{L})|(?<=\p{L})'/gu, '’')
    .replace(/(?<=^|[\s([{—–-])'(?=\d\ds\b)/gu, '’')
    .replace(/(?<=^|[\s([{—–-])'(?=\S)/gu, '‘')
    .replace(/(?<=^|[\s([{—–-])"(?=\S)/gu, '“')
    .replace(/(?<=[\p{L}.,;:!?…)\]’])"/gu, '”');
}

/**
 * A copy of `meta` with smartQuotes applied to what visitors read outside the notes: the title and
 * description, each variant's label and description, each source's title, topic and author, and the
 * franchise. Values that are not strings are left for the schema to report.
 */
export function typesetMeta(meta: Meta): Meta {
  const q = (v: unknown) => (typeof v === 'string' ? smartQuotes(v) : v);
  const pick = (v: unknown, keys: string[]) =>
    isMapping(v)
      ? { ...v, ...Object.fromEntries(keys.filter((k) => k in v).map((k) => [k, q(v[k])])) }
      : v;
  const out = pick(meta, ['title', 'description']) as Meta;
  if (Array.isArray(meta.sources))
    out.sources = meta.sources.map((s) => pick(s, ['title', 'topic', 'author']));
  if ('franchise' in meta) out.franchise = pick(meta.franchise, ['title', 'owner']);
  if (isMapping(meta.variants)) {
    out.variants = Object.fromEntries(
      Object.entries(meta.variants).map(([name, e]) => [name, pick(e, ['label', 'description'])]),
    );
  }
  return out;
}
