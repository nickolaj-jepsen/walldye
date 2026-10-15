/**
 * The index's filter state, kept in the address with nuqs under the query names the Astro site used:
 * `q`, `sort`, `shape` and one repeated `<facet>=<value>` per checked box. Updates replace the
 * history entry and never reach the server. Readers suspend while prerendering, so they sit under
 * a `<Suspense>`.
 */
import { parseAsNativeArrayOf, parseAsString, parseAsStringLiteral, useQueryStates } from 'nuqs';
import { useSyncExternalStore } from 'react';
import { deviceAspect } from '../../client/screen';
import { type Aspect, SORT_ORDERS } from '../../lib/content';
import { type FilterDefaults, type FilterState, filterQuery, filterState } from './filter';

const PARSERS = {
  q: parseAsString.withDefault(''),
  sort: parseAsStringLiteral(SORT_ORDERS),
  shape: parseAsString,
  technique: parseAsNativeArrayOf(parseAsString),
  subject: parseAsNativeArrayOf(parseAsString),
  lineage: parseAsNativeArrayOf(parseAsString),
  other: parseAsNativeArrayOf(parseAsString),
};

/** The address's filter state, and a setter that writes a state back with its defaults left out. */
export function useIndexState(
  defaults: FilterDefaults,
): [FilterState, (next: FilterState) => void] {
  const [query, setQuery] = useQueryStates(PARSERS, { history: 'replace', scroll: false });
  const state = filterState(query, defaults);
  const set = (next: FilterState) => {
    const q = filterQuery(next, defaults);
    void setQuery({ ...q, q: q.q || null });
  };
  return [state, set];
}

/** The device's shape, read once per page load as the Astro index did. */
let home: Aspect | undefined;
const deviceShape = () => {
  home ??= deviceAspect();
  return home;
};
const never = () => () => {};
const wide = (): Aspect => '16:9';

/** deviceAspect(), or 16:9 while hydrating server HTML. */
export function useDeviceAspect(): Aspect {
  return useSyncExternalStore(never, deviceShape, wide);
}

/** Whether `query` matches; true while hydrating server HTML. */
export function useMedia(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const m = matchMedia(query);
      m.addEventListener('change', onChange);
      return () => m.removeEventListener('change', onChange);
    },
    () => matchMedia(query).matches,
    () => true,
  );
}
