import assert from 'node:assert/strict';
import { describe, it } from 'vitest';
import { FILTER_BOOT, SHAPE_BOOT } from './boot';
import {
  cleared,
  countFor,
  type FilterDefaults,
  type FilterQuery,
  filterQuery,
  filterState,
  type IndexItem,
  matches,
  ordered,
  resultText,
  summaryText,
  toggled,
} from './filter';

const DEFAULTS: FilterDefaults = {
  sort: 'featured',
  shape: '16:9',
  sorts: ['featured', 'newest', 'title'],
};
const EMPTY: FilterQuery = {
  q: '',
  sort: null,
  shape: null,
  technique: [],
  subject: [],
  lineage: [],
  other: [],
};

function item(slug: string, facets: string[], extra: Partial<IndexItem> = {}): IndexItem {
  return {
    slug,
    title: slug,
    added: '2026-01-01',
    views: 0,
    recent: 0,
    alt: '',
    sources: [],
    versions: [],
    facets,
    search: slug,
    focus: [0.5, 0.5],
    plates: { '16:9': { dark: 'a', light: 'a' } },
    ...extra,
  };
}

const ITEMS = [
  item('moon', ['technique:line', 'subject:space']),
  item('sea', ['technique:dither', 'subject:water']),
  item('star', ['technique:line', 'subject:space', 'other:claude']),
];

describe('the address', () => {
  it('falls back to the defaults for a missing or unknown sort and shape', () => {
    const s = filterState({ ...EMPTY, sort: 'views', shape: '4x3' }, DEFAULTS);
    assert.equal(s.sort, 'featured');
    assert.equal(s.shape, '16:9');
    assert.equal(filterState({ ...EMPTY, shape: '9x19.5' }, DEFAULTS).shape, '9:19.5');
  });

  it('leaves out a blank search and the default sort and shape', () => {
    const s = filterState({ ...EMPTY, q: '  ', sort: 'title', shape: '21x9' }, DEFAULTS);
    assert.deepEqual(filterQuery(s, DEFAULTS), { ...EMPTY, sort: 'title', shape: '21x9' });
    assert.deepEqual(filterQuery(filterState(EMPTY, DEFAULTS), DEFAULTS), EMPTY);
  });

  it('clears the search, boxes and sort and keeps the shape', () => {
    const s = filterState(
      { ...EMPTY, q: 'x', sort: 'title', shape: '21x9', subject: ['space'] },
      DEFAULTS,
    );
    assert.deepEqual(filterQuery(cleared(s, DEFAULTS), DEFAULTS), { ...EMPTY, shape: '21x9' });
  });
});

describe('filtering', () => {
  it('ORs within a facet and ANDs across facets', () => {
    const s = filterState(
      { ...EMPTY, technique: ['line', 'dither'], subject: ['space'] },
      DEFAULTS,
    );
    assert.deepEqual(
      ITEMS.filter((it) => matches(it, s)).map((it) => it.slug),
      ['moon', 'star'],
    );
  });

  it('counts a box against the other facets only', () => {
    const s = filterState({ ...EMPTY, subject: ['space'] }, DEFAULTS);
    assert.equal(countFor(ITEMS, s, 'subject', 'water'), 1);
    assert.equal(countFor(ITEMS, s, 'technique', 'dither'), 0);
  });

  it('searches the normalized text', () => {
    const s = filterState({ ...EMPTY, q: ' MÓON ' }, DEFAULTS);
    assert.deepEqual(
      ITEMS.filter((it) => matches(it, s)).map((it) => it.slug),
      ['moon'],
    );
  });

  it('toggles a box in check order', () => {
    let s = filterState(EMPTY, DEFAULTS);
    s = toggled(s, 'subject', 'water', true);
    s = toggled(s, 'subject', 'space', true);
    assert.deepEqual(s.facets.subject, ['water', 'space']);
    assert.deepEqual(toggled(s, 'subject', 'water', false).facets.subject, ['space']);
  });

  it('puts featured pieces first', () => {
    const items = [item('b', []), item('a', [], { featured: 0 })];
    assert.deepEqual(
      ordered(items, 'featured').map((it) => it.slug),
      ['a', 'b'],
    );
  });
});

describe('the words', () => {
  it('names the results by the total', () => {
    assert.equal(resultText(3, 3), '3 wallpapers');
    assert.equal(resultText(0, 1), '0 of 1 wallpaper');
  });

  it('summarizes the search and the checked labels in form order', () => {
    const groups = [
      {
        facet: 'subject' as const,
        legend: 'Subject',
        entries: [
          { value: 'space', label: 'Space', count: 2 },
          { value: 'water', label: 'Water', count: 1 },
        ],
      },
    ];
    const s = filterState({ ...EMPTY, q: 'moon ', subject: ['water', 'space'] }, DEFAULTS);
    assert.equal(summaryText(s, groups), '“moon”, Space, Water');
  });
});

describe('the inline scripts', () => {
  it('parse', () => {
    assert.doesNotThrow(() => new Function(SHAPE_BOOT));
    assert.doesNotThrow(() => new Function(FILTER_BOOT));
  });
});
