/**
 * The index filter as pure functions: search over the normalised `search` text, OR within a facet,
 * AND across facets, and the orders of comparePieces().
 *
 * The query string is the facets form's own GET serialisation: `q=<text>`, `sort=<order>` and one
 * `<facet>=<value>` per checked box, in form order.
 */
import {
  comparePieces,
  isSortOrder,
  normaliseSearch,
  type SortKey,
  type SortOrder,
} from '../../lib/content';

export interface FilterState {
  /** Search text as typed. */
  q: string;
  sort: SortOrder;
  /** Checked values per facet. */
  facets: Map<string, Set<string>>;
}

/** One filterable piece: an index `li`. */
export interface Filterable extends SortKey {
  /** `facet:value` pairs. */
  facets: ReadonlySet<string>;
  /** normaliseSearch() of the searchable text. */
  search: string;
}

/** The filter state in `params`: `q`, `sort` (newest when absent or unknown) and every other key as a facet. */
export function filterState(params: URLSearchParams): FilterState {
  const facets = new Map<string, Set<string>>();
  for (const [key, value] of params) {
    if (key !== 'q' && key !== 'sort') facets.set(key, (facets.get(key) ?? new Set()).add(value));
  }
  const sort = params.get('sort');
  return { q: params.get('q') ?? '', sort: isSortOrder(sort) ? sort : 'newest', facets };
}

/** The address's query string for the form's `params`, without a blank search or the default sort. */
export function filterQuery(params: URLSearchParams): string {
  const out = new URLSearchParams(params);
  if (!out.get('q')?.trim()) out.delete('q');
  if (out.get('sort') === 'newest') out.delete('sort');
  return out.toString();
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
export function countFor(
  items: readonly Filterable[],
  state: FilterState,
  facet: string,
  value: string,
): number {
  const pair = `${facet}:${value}`;
  let n = 0;
  for (const it of items) if (it.facets.has(pair) && matches(it, state, facet)) n++;
  return n;
}

/** `items` in the state's sort order (comparePieces). */
export function ordered<T extends SortKey>(items: readonly T[], sort: SortOrder): T[] {
  return items.slice().sort((a, b) => comparePieces(a, b, sort));
}
