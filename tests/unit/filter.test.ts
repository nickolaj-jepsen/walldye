import { describe, expect, it } from 'vitest';
import {
  countFor,
  type Filterable,
  type FilterDefaults,
  filterQuery,
  filterState,
  matches,
  ordered,
} from '../../src/client/index/filter';
import { normalizeSearch } from '../../src/lib/content';

const item = (
  slug: string,
  title: string,
  added: string,
  facets: string[],
  search = title.toLowerCase(),
  views = 0,
  recent = 0,
): Filterable => ({
  slug,
  title,
  added,
  views,
  recent,
  facets: new Set(facets),
  search,
});

const DEFAULTS: FilterDefaults = { sort: 'newest', shape: '16:9' };

const ITEMS = [
  item('a', 'Zebra', '2026-01-01', ['technique:dither', 'subject:space'], 'zebra', 90, 1.5),
  item(
    'b',
    'apple',
    '2026-03-01',
    ['technique:drafting', 'subject:maps', 'other:any-screen'],
    'apple',
    10,
    6,
  ),
  item('c', 'Mango', '2026-03-01', ['technique:dither', 'subject:maps'], 'mango', 10, 6),
  item('d', 'Éclair', '2026-02-01', ['technique:glyph'], 'eclair by georg nees', 40, 9.25),
];

describe('filterState / filterQuery', () => {
  it('reads the form serialization, every key but q, sort and shape as a facet', () => {
    const s = filterState(
      new URLSearchParams(
        'q=moon&sort=title&shape=21x9&technique=dither&subject=maps&technique=drafting',
      ),
      DEFAULTS,
    );
    expect(s.q).toBe('moon');
    expect(s.sort).toBe('title');
    expect(s.shape).toBe('21:9');
    expect([...(s.facets.get('technique') ?? [])]).toEqual(['dither', 'drafting']);
    expect([...(s.facets.get('subject') ?? [])]).toEqual(['maps']);
    expect(s.facets.has('q')).toBe(false);
    expect(s.facets.has('shape')).toBe(false);
  });

  it('reads each sort order and treats any other as the default', () => {
    for (const sort of ['newest', 'popular', 'views', 'title'] as const) {
      expect(filterState(new URLSearchParams({ sort }), DEFAULTS).sort).toBe(sort);
    }
    expect(filterState(new URLSearchParams('sort=oldest'), DEFAULTS).sort).toBe('newest');
    const popular = { ...DEFAULTS, sort: 'popular' } as const;
    expect(filterState(new URLSearchParams(), popular).sort).toBe('popular');
  });

  it('reads the shape and treats an unknown one as the default', () => {
    expect(filterState(new URLSearchParams('shape=9x19.5'), DEFAULTS).shape).toBe('9:19.5');
    expect(filterState(new URLSearchParams('shape=4x3'), DEFAULTS).shape).toBe('16:9');
    const phone = { ...DEFAULTS, shape: '9:19.5' } as const;
    expect(filterState(new URLSearchParams(), phone).shape).toBe('9:19.5');
  });

  it('leaves out a blank search and the default sort and shape, and keeps the form order', () => {
    expect(filterQuery(new URLSearchParams('q=%20%20&sort=newest&shape=16x9'), DEFAULTS)).toBe('');
    expect(
      filterQuery(
        new URLSearchParams(
          'q=moon&sort=title&shape=10x16&technique=drafting&technique=dither&subject=maps',
        ),
        DEFAULTS,
      ),
    ).toBe('q=moon&sort=title&shape=10x16&technique=drafting&technique=dither&subject=maps');
    const popular = { sort: 'popular', shape: '9:19.5' } as const;
    expect(filterQuery(new URLSearchParams('sort=popular&shape=9x19.5'), popular)).toBe('');
    expect(filterQuery(new URLSearchParams('sort=newest&shape=16x9'), popular)).toBe(
      'sort=newest&shape=16x9',
    );
  });
});

describe('matches / countFor', () => {
  it('is OR within a facet and AND across facets', () => {
    const s = filterState(
      new URLSearchParams('technique=dither&technique=drafting&subject=maps'),
      DEFAULTS,
    );
    expect(ITEMS.filter((it) => matches(it, s)).map((it) => it.slug)).toEqual(['b', 'c']);
  });

  it('searches the normalized text', () => {
    const s = filterState(new URLSearchParams('q=  GEORG   Nées '), DEFAULTS);
    expect(ITEMS.filter((it) => matches(it, s)).map((it) => it.slug)).toEqual(['d']);
  });

  it("matches typewriter and typographer's apostrophes alike", () => {
    const baldur = item('e', 'Baldur’s Gate', '2026-02-01', [], normalizeSearch('Baldur’s Gate'));
    for (const q of ["baldur's", 'Baldur’s gate']) {
      expect(matches(baldur, filterState(new URLSearchParams({ q }), DEFAULTS))).toBe(true);
    }
  });

  it('counts a box against the other facets only', () => {
    const s = filterState(new URLSearchParams('technique=dither&subject=maps'), DEFAULTS);
    // Adding drafting to the technique group would show b; the subject group still applies.
    expect(countFor(ITEMS, s, 'technique', 'drafting')).toBe(1);
    expect(countFor(ITEMS, s, 'technique', 'glyph')).toBe(0);
    expect(countFor(ITEMS, s, 'subject', 'space')).toBe(1);
    expect(countFor(ITEMS, s, 'other', 'any-screen')).toBe(0);
  });
});

describe('ordered', () => {
  it('sorts newest first or by title, ties by slug', () => {
    expect(ordered(ITEMS, 'newest').map((it) => it.slug)).toEqual(['b', 'c', 'd', 'a']);
    expect(ordered(ITEMS, 'title').map((it) => it.slug)).toEqual(['b', 'd', 'c', 'a']);
  });

  it('sorts by recent or all views, ties by newest then slug', () => {
    expect(ordered(ITEMS, 'popular').map((it) => it.slug)).toEqual(['d', 'b', 'c', 'a']);
    expect(ordered(ITEMS, 'views').map((it) => it.slug)).toEqual(['a', 'd', 'b', 'c']);
    const unseen = [item('x', 'X', '2026-01-01', []), item('y', 'Y', '2026-05-01', [])];
    expect(ordered(unseen, 'popular').map((it) => it.slug)).toEqual(['y', 'x']);
  });
});
