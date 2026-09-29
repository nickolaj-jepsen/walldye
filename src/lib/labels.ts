/**
 * The words visitors see for taxonomy slugs, computed facets, model ids and licences. The content
 * schema fails the build when a published piece uses a value with no label here. Facet entries are
 * lowercase: they are index entries, not headings.
 */

/** Facets that meta.yaml fills from taxonomy.yaml, in the order the index shows them. */
export const TAXONOMY_FACETS = ['technique', 'subject', 'lineage'] as const;
export type TaxonomyFacet = (typeof TAXONOMY_FACETS)[number];

/** Every facet the index filters on: the taxonomy facets plus `other`, the computed ones. */
export type Facet = TaxonomyFacet | 'other';

export const FACET_LEGENDS: Record<Facet, string> = {
  technique: 'Technique',
  subject: 'Subject',
  lineage: 'Inspired by',
  other: 'Other',
};

export const FACET_LABELS: Record<TaxonomyFacet, Record<string, string>> = {
  technique: {
    dither: 'dithering',
    pixel: 'pixel art',
    glyph: 'text characters',
    drafting: 'technical drawing',
    instrument: 'instrument displays',
    tiling: 'tiling',
    simulation: 'simulations',
    stipple: 'stippling and hatching',
    field: 'flow fields and contours',
    flat: 'flat shapes',
    line: 'line art',
  },
  subject: {
    space: 'space',
    landscape: 'landscape',
    physics: 'physics',
    maps: 'maps',
    computing: 'computing',
    textile: 'textiles',
    games: 'games',
    maths: 'mathematics',
    'flora-fauna': 'plants and animals',
    machines: 'machines',
    architecture: 'architecture',
    music: 'music and sound',
    sport: 'sport',
  },
  lineage: {
    'early-computer-art': 'early computer art',
    'op-art': 'op art',
    modernism: 'modernism',
    'creative-coding': 'creative coding',
    'japanese-art': 'Japanese art',
    'patent-drawings': 'patent drawings',
    'scientific-illustration': 'scientific illustration',
    'vintage-computers': 'vintage computers',
    'arcade-games': 'arcade games',
  },
};

/** Computed facets (the "Other" group): query value -> label. */
export const OTHER_LABELS = {
  references: 'has references',
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
 * The credit name for each meta.yaml `model:` id, shown as "Made with {name}". A model missing
 * here fails the build (walldye check reads this table too).
 */
export const MODEL_NAMES: Record<string, string> = {
  'claude-opus-5-5': 'Claude Opus 5.5',
};

/** Where takedown requests for fan works go, shown in the fan-work line. */
export const TAKEDOWN_CONTACT = 'takedown@walldye.com';

/**
 * The plain-words line under the credit for licences other than the default (CC0-1.0, which
 * shows nothing); no licence names or identifiers. A licence missing here fails the build. The
 * fan-work line is built by the detail page from `franchise` and TAKEDOWN_CONTACT.
 */
export const LICENCE_LINES: Record<string, string> = {
  // "Above" is the caption's "after …" line and the credit, which reuse under CC BY has to keep.
  'CC-BY-4.0': 'Free to use, with credit as given above.',
  'CC-BY-SA-3.0':
    'Free to use, with credit as given above; a changed version must be shared on the same terms.',
};
