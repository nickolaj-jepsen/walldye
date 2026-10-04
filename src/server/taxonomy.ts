import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  type Facet,
  OTHER_LABELS,
  type OtherValue,
  TAXONOMY_FACETS,
  type TaxonomyFacet,
} from '../lib/labels';
import { parseYaml } from './yaml';

/** taxonomy.yaml: the words visitors see for each facet value, and each model id's credit name. */
export interface Taxonomy {
  facets: Record<TaxonomyFacet, Record<string, string>>;
  models: Record<string, string>;
}

function labels(value: unknown, what: string): Record<string, string> {
  if (value == null) return {};
  const ok =
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === 'string' && v.trim() !== '');
  if (!ok) throw new Error(`taxonomy.yaml: ${what} must map each value to its words`);
  return value as Record<string, string>;
}

/** The wallpapers/taxonomy.yaml of `root`; throws naming the part that is malformed. */
export function loadTaxonomy(root = resolve('.')): Taxonomy {
  const text = readFileSync(join(root, 'wallpapers', 'taxonomy.yaml'), 'utf8');
  const data = (parseYaml(text) ?? {}) as Record<string, unknown>;
  const facets = {} as Taxonomy['facets'];
  for (const facet of TAXONOMY_FACETS) facets[facet] = labels(data[facet], facet);
  return { facets, models: labels(data.models, 'models') };
}

// Astro runs from the project root.
export const TAXONOMY = loadTaxonomy();

/** The words visitors see for a facet value, or undefined when it has none. */
export function facetLabel(facet: Facet, value: string): string | undefined {
  if (facet === 'other') return OTHER_LABELS[value as OtherValue];
  return TAXONOMY.facets[facet][value];
}
