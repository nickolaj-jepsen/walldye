/**
 * The index filter as pure functions: search over the normalised
 * `search` text, OR within a facet, AND across facets, and the orders of comparePieces().
 *
 * The query string is the facets form's own GET serialisation: `q=<text>`, `sort=<order>` (left out
 * for newest) and one `<facet>=<value>` per checked box.
 */
import { comparePieces, isSortOrder, normaliseSearch, type SortKey, type SortOrder } from '../lib/content';

/** Query keys that carry facet values, in the order the index form lists them. */
export const FILTER_FACETS = ['technique', 'subject', 'lineage', 'other'] as const;

export interface FilterState {
  /** Search text as typed. */
  q: string;
  sort: SortOrder;
  /** Checked values per facet, in the order they were added. */
  facets: Map<string, Set<string>>;
}

/** One filterable piece: an index `li`. */
export interface Filterable extends SortKey {
  /** `facet:value` pairs. */
  facets: ReadonlySet<string>;
  /** normaliseSearch() of the searchable text. */
  search: string;
}

/**
 * The filter state in `params`. `accept(facet, value)` drops values the index has no box for, and
 * `accept('sort', order)` orders it has no radio for; an unknown or dropped `sort` means newest.
 */
export function parseQuery(params: URLSearchParams, accept: (facet: string, value: string) => boolean = () => true): FilterState {
  const facets = new Map<string, Set<string>>();
  for (const facet of FILTER_FACETS) {
    for (const value of params.getAll(facet)) {
      if (!accept(facet, value)) continue;
      if (!facets.has(facet)) facets.set(facet, new Set());
      facets.get(facet)!.add(value);
    }
  }
  const sort = params.get('sort');
  return { q: params.get('q') ?? '', sort: isSortOrder(sort) && accept('sort', sort) ? sort : 'newest', facets };
}

/**
 * The query string for `state` without a leading `?`, empty for the unfiltered default. Facet values
 * follow `order` (the form's box order) when given, else FILTER_FACETS order and insertion order.
 */
export function serialiseQuery(state: FilterState, order?: readonly (readonly [facet: string, value: string])[]): string {
  const params = new URLSearchParams();
  if (state.q.trim()) params.append('q', state.q);
  if (state.sort !== 'newest') params.append('sort', state.sort);
  const pairs = order ?? FILTER_FACETS.flatMap((f) => [...(state.facets.get(f) ?? [])].map((v) => [f, v] as const));
  for (const [facet, value] of pairs) if (state.facets.get(facet)?.has(value)) params.append(facet, value);
  return params.toString();
}

/** Whether `item` passes the search and every facet group except `skip`. */
export function matches(item: Filterable, state: FilterState, skip?: string): boolean {
  const needle = normaliseSearch(state.q);
  if (needle && !item.search.includes(needle)) return false;
  for (const [facet, values] of state.facets) {
    if (facet === skip || values.size === 0) continue;
    let any = false;
    for (const v of values) if (item.facets.has(`${facet}:${v}`)) any = true;
    if (!any) return false;
  }
  return true;
}

/** How many of `items` a box would show: they pass the other facets and the search, and carry `facet:value`. */
export function countFor(items: readonly Filterable[], state: FilterState, facet: string, value: string): number {
  const pair = `${facet}:${value}`;
  let n = 0;
  for (const it of items) if (it.facets.has(pair) && matches(it, state, facet)) n++;
  return n;
}

/** `items` in the state's sort order (comparePieces). */
export function ordered<T extends SortKey>(items: readonly T[], sort: SortOrder): T[] {
  return items.slice().sort((a, b) => comparePieces(a, b, sort));
}
