/**
 * The words visitors see for the facets, the computed facet values and licenses. The taxonomy
 * values and model ids have theirs in taxonomy.yaml (src/server/taxonomy.ts reads it).
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

/** Computed facets (the "Other" group): query value -> label. */
export const OTHER_LABELS = {
  references: 'has references',
  'any-screen': 'fits any screen',
  'source-code': 'has source code',
  claude: 'made with Claude',
  'human-made': 'human-made',
} as const;
export type OtherValue = keyof typeof OTHER_LABELS;

/** Where takedown requests for fan works go, shown in the fan-work line. */
export const TAKEDOWN_CONTACT = 'takedown@walldye.com';

/**
 * The plain-words line under the credit for licenses other than the default (CC0-1.0, which
 * shows nothing); no license names or identifiers. A license missing here fails the build. The
 * fan-work line is built by the detail page from `franchise` and TAKEDOWN_CONTACT.
 */
export const LICENSE_LINES: Record<string, string> = {
  // "Above" is the caption's "after …" line and the credit, which reuse under CC BY has to keep.
  'CC-BY-4.0': 'Free to use, with credit as given above.',
  'CC-BY-SA-3.0':
    'Free to use, with credit as given above; a changed version must be shared on the same terms.',
};
