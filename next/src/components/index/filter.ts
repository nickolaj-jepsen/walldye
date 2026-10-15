/**
 * The index filter as pure functions: search over the normalized `search` text, OR within a facet,
 * AND across facets, the orders of comparePieces(), and the words the results line and the phone
 * summary show.
 */
import type { PlateData, PlateRef, TemplateInfo } from '../../lib/catalog';
import {
  type Aspect,
  aspectLabel,
  aspectOfLabel,
  comparePieces,
  type FilterGroup,
  isSortOrder,
  normalizeSearch,
  type Piece,
  type SortKey,
  type SortOrder,
} from '../../lib/content';
import type { Facet } from '../../lib/labels';

/** The facets the index filters on, in form order; each is its own repeated query key. */
export const FACETS = ['technique', 'subject', 'lineage', 'other'] as const satisfies Facet[];

/** What the index knows of one piece: the sort keys, what the filter reads and what its entry shows. */
export interface IndexItem extends SortKey {
  alt: string;
  sources: Piece['sources'];
  /** The versions' draft flags: their count and how many are drafts, for the caption. */
  versions: readonly { draft: boolean }[];
  /** `facet:value` pairs (facetPairs). */
  facets: readonly string[];
  /** normalizeSearch() of the searchable text (searchText). */
  search: string;
  /** The 16:9 template's focus, fractions of the canvas. */
  focus: readonly [number, number];
  /** The default version's templates by shape; a shape without one is a crop of 16:9. */
  plates: Piece['plates'];
}

export interface FilterState {
  /** Search text as typed. */
  q: string;
  sort: SortOrder;
  /** The shape the plates are shown in. */
  shape: Aspect;
  /** Checked values per facet. */
  facets: Readonly<Record<Facet, readonly string[]>>;
}

/** The query string's values as nuqs parses them: null where the key is absent. */
export interface FilterQuery {
  q: string;
  sort: SortOrder | null;
  shape: string | null;
  technique: string[];
  subject: string[];
  lineage: string[];
  other: string[];
}

/** What a query without a sort or shape means: the build's first order and the device's shape. */
export interface FilterDefaults {
  sort: SortOrder;
  shape: Aspect;
  /** The orders the form offers; any other in the address falls back to `sort`. */
  sorts: readonly SortOrder[];
}

/** The state `query` names, with the defaults' sort and shape where it has none or an unknown one. */
export function filterState(query: FilterQuery, defaults: FilterDefaults): FilterState {
  const sort = isSortOrder(query.sort) && defaults.sorts.includes(query.sort) ? query.sort : null;
  return {
    q: query.q,
    sort: sort ?? defaults.sort,
    shape: aspectOfLabel(query.shape) ?? defaults.shape,
    facets: {
      technique: query.technique,
      subject: query.subject,
      lineage: query.lineage,
      other: query.other,
    },
  };
}

/** The query values for `state`: a blank search, the default sort and the default shape are left out. */
export function filterQuery(state: FilterState, defaults: FilterDefaults): FilterQuery {
  return {
    q: state.q.trim() ? state.q : '',
    sort: state.sort === defaults.sort ? null : state.sort,
    shape: state.shape === defaults.shape ? null : aspectLabel(state.shape),
    technique: [...state.facets.technique],
    subject: [...state.facets.subject],
    lineage: [...state.facets.lineage],
    other: [...state.facets.other],
  };
}

/** The state with no search or facet, keeping the shape; the sort goes back to the default. */
export function cleared(state: FilterState, defaults: FilterDefaults): FilterState {
  return {
    q: '',
    sort: defaults.sort,
    shape: state.shape,
    facets: { technique: [], subject: [], lineage: [], other: [] },
  };
}

/** `state` with `value` of `facet` checked or not, in the order the boxes were checked. */
export function toggled(state: FilterState, facet: Facet, value: string, on: boolean): FilterState {
  const rest = state.facets[facet].filter((v) => v !== value);
  return { ...state, facets: { ...state.facets, [facet]: on ? [...rest, value] : rest } };
}

/** Whether `item` passes the search and every facet group except `skip`. */
export function matches(item: IndexItem, state: FilterState, skip?: Facet): boolean {
  const needle = normalizeSearch(state.q);
  if (needle && !item.search.includes(needle)) return false;
  for (const facet of FACETS) {
    const values = state.facets[facet];
    if (facet === skip || values.length === 0) continue;
    if (!values.some((v) => item.facets.includes(`${facet}:${v}`))) return false;
  }
  return true;
}

/** How many of `items` a box would show: they pass the other facets and the search, and carry `facet:value`. */
export function countFor(
  items: readonly IndexItem[],
  state: FilterState,
  facet: Facet,
  value: string,
): number {
  const pair = `${facet}:${value}`;
  let n = 0;
  for (const it of items) if (it.facets.includes(pair) && matches(it, state, facet)) n++;
  return n;
}

/** `items` in `sort` order (comparePieces). */
export function ordered<T extends SortKey>(items: readonly T[], sort: SortOrder): T[] {
  return items.slice().sort((a, b) => comparePieces(a, b, sort));
}

/** "12 wallpapers", or "3 of 12 wallpapers" while filtered; the noun follows the total. */
export function resultText(shown: number, total: number): string {
  const noun = total === 1 ? 'wallpaper' : 'wallpapers';
  return shown === total ? `${total} ${noun}` : `${shown} of ${total} ${noun}`;
}

/** The phone filter button: "Show 3 wallpapers". */
export function showText(shown: number): string {
  return `Show ${shown} ${shown === 1 ? 'wallpaper' : 'wallpapers'}`;
}

/** The closed filter's summary: the search in quotes, then the checked entries' labels in form order. */
export function summaryText(state: FilterState, groups: readonly FilterGroup[]): string {
  const terms: string[] = [];
  const needle = state.q.trim();
  if (needle) terms.push(`“${needle}”`);
  for (const g of groups) {
    for (const e of g.entries) if (state.facets[g.facet].includes(e.value)) terms.push(e.label);
  }
  return terms.join(', ');
}

/** The template facts of `ref` from `templates`, as the server's resolvePlate() gives them. */
export function plateData(
  templates: Readonly<Record<string, TemplateInfo>>,
  ref: PlateRef,
): PlateData {
  return {
    dark: { hash: ref.dark, ...templates[ref.dark] },
    light: { hash: ref.light, ...templates[ref.light] },
  };
}
