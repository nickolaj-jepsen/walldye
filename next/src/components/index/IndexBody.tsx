'use client';
/**
 * The index under its heading: the filter form (search, sort, shape and the facet boxes with live
 * counts), the Colors row, the results line and the grid in the state's order and shape, the
 * entries the filter leaves out hidden rather than removed. Without `onChange` it is the
 * prerendered page for the default state, carrying the inline `boot` scripts.
 */
import type { Route } from 'next';
import {
  type ChangeEvent,
  type CSSProperties,
  memo,
  type ReactNode,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from 'react';
import { flushSync } from 'react-dom';
import { WIDE_QUERY } from '../../client/screen';
import type { TemplateInfo } from '../../lib/catalog';
import {
  type Aspect,
  aspectLabel,
  CANVAS,
  type FilterGroup,
  SITE_ASPECTS,
  type SortOrder,
} from '../../lib/content';
import { cropBox, focusPosition } from '../../lib/shape';
import { GridPlate } from '../grid/GridPlate';
import {
  cleared,
  countFor,
  type FilterDefaults,
  type FilterState,
  type IndexItem,
  matches,
  ordered,
  plateData,
  resultText,
  showText,
  summaryText,
  toggled,
} from './filter';
import { ThemeRow } from './ThemeRow';
import { useMedia } from './use-index-state';

/** Plates drawn at once on load: about the first screen of a wide grid. */
const EAGER = 8;

const SORT_LABELS: Record<SortOrder, string> = {
  featured: 'featured',
  newest: 'newest',
  popular: 'popular',
  views: 'most viewed',
  title: 'title',
};

export interface IndexData {
  /** Every piece, in any order. */
  items: readonly IndexItem[];
  /** The templates the items' plates name, by hash. */
  templates: Readonly<Record<string, TemplateInfo>>;
  /** The facet boxes, with their unfiltered counts. */
  groups: readonly FilterGroup[];
}

export interface IndexBodyProps extends IndexData {
  state: FilterState;
  defaults: FilterDefaults;
  /** The shape plate links leave out of their address. */
  home: Aspect;
  /** Takes the state the visitor set; absent while prerendered. */
  onChange?: (next: FilterState) => void;
  /** Inline scripts for the prerendered page: after the filter, and first in the plates section. */
  boot?: { filter: ReactNode; shape: ReactNode };
}

interface EntryProps {
  item: IndexItem;
  templates: IndexData['templates'];
  shape: Aspect;
  home: Aspect;
  eager: boolean;
  hidden: boolean;
}

/** One index entry in `shape`: its template of that shape, else 16:9's cropped around its focus. */
const Entry = memo(function Entry({ item, templates, shape, home, eager, hidden }: EntryProps) {
  const own = item.plates[shape];
  const data = plateData(templates, own ?? item.plates['16:9']);
  const view = own ? undefined : cropBox(shape, focusPosition(shape, item.focus));
  const href = (
    shape === home ? `/${item.slug}` : `/${item.slug}?shape=${aspectLabel(shape)}`
  ) as Route;
  return (
    <GridPlate
      piece={item}
      data={data}
      view={view}
      href={href}
      eager={eager}
      hidden={hidden}
      transitionName={`plate-${item.slug}`}
    />
  );
});

const noop = () => {};

export function IndexBody({
  items,
  templates,
  groups,
  state,
  defaults,
  home,
  onChange = noop,
  boot,
}: IndexBodyProps) {
  const total = items.length;
  // Typing stays responsive while the grid catches up.
  const shown = useDeferredValue(state);
  const passing = new Set(items.filter((it) => matches(it, shown)).map((it) => it.slug));
  const count = passing.size;
  let rank = 0;
  const sorted = ordered(items, shown.sort).map((it) => {
    const pass = passing.has(it.slug);
    return { it, pass, eager: pass && rank++ < EAGER };
  });

  // The count becomes a live region only once it matches the address, so a filtered load is not announced.
  const [live, setLive] = useState(false);
  useEffect(() => setLive(true), []);

  const wide = useMedia(WIDE_QUERY);
  // A toggle holds until the screen crosses the wide break, which opens or closes the filter.
  const [toggle, setToggle] = useState<{ open: boolean; wide: boolean } | null>(null);
  const open = toggle && toggle.wide === wide ? toggle.open : wide;
  const summary = useRef<HTMLElement>(null);

  const search = (e: ChangeEvent<HTMLInputElement>) => onChange({ ...state, q: e.target.value });

  // Phones: close the filter and bring its summary, the Colors row and the grid into view.
  const showResults = () => {
    flushSync(() => setToggle({ open: false, wide }));
    summary.current?.focus({ preventScroll: true });
    summary.current?.scrollIntoView({ block: 'start' });
  };

  const [w, h] = CANVAS[shown.shape];
  return (
    <>
      <details
        className="filter"
        open={boot ? true : open}
        onToggle={(e) => setToggle({ open: e.currentTarget.open, wide })}
      >
        <summary ref={summary}>
          <span className="sc">Filter</span>
          <span className="state">{summaryText(state, groups)}</span>
        </summary>
        {/* biome-ignore lint/a11y/useSemanticElements: the form itself is the landmark, and the reset button targets it */}
        <form
          id="facets"
          className="facets"
          role="search"
          aria-label="Filter wallpapers"
          action="/"
          method="get"
          onSubmit={(e) => e.preventDefault()}
          onReset={(e) => {
            // "clear" clears the search and the boxes; the shape is kept.
            e.preventDefault();
            onChange(cleared(state, defaults));
          }}
        >
          <div className="search">
            <label className="label sc" htmlFor="q">
              Search
            </label>
            <input
              id="q"
              name="q"
              type="search"
              placeholder="title, artist or description"
              autoComplete="off"
              value={state.q}
              onChange={search}
            />
          </div>
          <fieldset>
            <legend className="sc">Sort</legend>
            <div className="seg">
              {defaults.sorts.map((s) => (
                <label key={s}>
                  <input
                    type="radio"
                    name="sort"
                    value={s}
                    checked={state.sort === s}
                    onChange={() => onChange({ ...state, sort: s })}
                  />
                  <span>{SORT_LABELS[s]}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="sc">Shape</legend>
            <div className="seg">
              {SITE_ASPECTS.map((a) => (
                <label key={a}>
                  <input
                    type="radio"
                    name="shape"
                    value={aspectLabel(a)}
                    checked={state.shape === a}
                    onChange={() => onChange({ ...state, shape: a })}
                  />
                  <span>
                    <span className="mono">{a}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          {groups.map((g) => (
            <fieldset key={g.facet}>
              <legend className="sc">{g.legend}</legend>
              {g.entries.map((e) => {
                const checked = state.facets[g.facet].includes(e.value);
                const n = countFor(items, state, g.facet, e.value);
                return (
                  <label key={e.value} className="entry">
                    <input
                      type="checkbox"
                      name={g.facet}
                      value={e.value}
                      checked={checked}
                      disabled={n === 0 && !checked}
                      onChange={(ev) =>
                        onChange(toggled(state, g.facet, e.value, ev.target.checked))
                      }
                    />
                    <span className="term">{e.label}</span>
                    <span className="leader" />
                    <span className="count">{n}</span>
                  </label>
                );
              })}
            </fieldset>
          ))}
        </form>
        <button type="button" className="textbtn show" onClick={showResults}>
          {showText(count)}
        </button>
      </details>
      {boot?.filter}
      <section
        className="plates"
        aria-label="Wallpapers"
        data-shape={shown.shape}
        data-tall={h > w ? '' : undefined}
        style={{ '--shape-ratio': w / h } as CSSProperties}
      >
        {boot?.shape}
        <ThemeRow />
        <p className="results-line">
          <span id="result-count" className="lnum" role={live ? 'status' : undefined}>
            {resultText(count, total)}
          </span>
          {/* site.css shows it only while a box is checked or the search holds text. */}
          <button type="reset" form="facets" className="textbtn clear">
            clear
          </button>
        </p>
        <p className="empty">Try fewer filters or a shorter search.</p>
        <ul className="grid">
          {sorted.map(({ it, pass, eager }) => (
            <Entry
              key={it.slug}
              item={it}
              templates={templates}
              shape={shown.shape}
              home={home}
              eager={eager}
              hidden={!pass}
            />
          ))}
        </ul>
      </section>
    </>
  );
}
