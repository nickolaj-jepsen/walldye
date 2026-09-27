/**
 * The words visitors see for taxonomy.yaml slugs, computed facets and licences.
 *
 * taxonomy.yaml and meta.yaml keep slugs; every value a published piece uses needs a label here,
 * and the content schema (src/content.config.ts) fails the build when one is missing.
 * Entries are lowercase: they are index entries, not headings.
 */

/** Facets that meta.yaml fills from taxonomy.yaml, in the order the index shows them. */
export const TAXONOMY_FACETS = ['technique', 'subject', 'lineage'] as const;
export type TaxonomyFacet = (typeof TAXONOMY_FACETS)[number];

/** Every facet the index filters on: the taxonomy facets plus `other`, the computed ones. */
export type Facet = TaxonomyFacet | 'other';

/** Fieldset legends. */
export const FACET_LEGENDS: Record<Facet, string> = {
  technique: 'Technique',
  subject: 'Subject',
  lineage: 'Inspired by',
  other: 'Other',
};

/** Display label per taxonomy value. */
export const FACET_LABELS: Record<TaxonomyFacet, Record<string, string>> = {
  technique: {
    dither: 'dithering',
    pixel: 'pixel art',
    glyph: 'text characters',
    drafting: 'technical drawing',
    instrument: 'instrument displays',
    tiling: 'tiling',
    simulation: 'simulations',
    stipple: 'stippling',
    field: 'flow fields and contours',
  },
  subject: {
    space: 'space',
    landscape: 'landscape',
    physics: 'physics',
    maps: 'maps',
    computing: 'computing',
    textile: 'textiles',
    games: 'games',
  },
  lineage: {
    'early-computer-art': 'early computer art',
  },
};

/** Values with no filter entry and no fact: the caption's "after …" line and "has references" already cover homage. */
export const UNLISTED: Record<TaxonomyFacet, readonly string[]> = {
  technique: [],
  subject: [],
  lineage: ['homage'],
};

/** Computed facets (the "Other" group): query value -> label. */
export const OTHER_LABELS = {
  references: 'has references',
  'light-themes': 'works in light themes',
  'any-screen': 'fits any screen',
  'source-code': 'has source code',
  claude: 'made with Claude',
  'human-made': 'human-made',
} as const;
export type OtherValue = keyof typeof OTHER_LABELS;

/** Label of a facet value, or undefined when it has none (the schema turns that into a build error). */
export function facetLabel(facet: Facet, value: string): string | undefined {
  if (facet === 'other') return OTHER_LABELS[value as OtherValue];
  return FACET_LABELS[facet][value];
}

/**
 * Where takedown requests for fan works go, shown in the fan-work line. Unset until the owner
 * chooses it (docs/design.md, Owner actions); a published fan-work piece fails the build meanwhile.
 */
export const TAKEDOWN_CONTACT: string | undefined = undefined;

/**
 * The plain-words line under the credit for licences other than the default (CC0-1.0, which
 * shows nothing); no licence names or identifiers. A licence missing here fails the build. The
 * fan-work line is built by the detail page from `franchise` and TAKEDOWN_CONTACT.
 */
export const LICENCE_LINES: Record<string, string> = {};

