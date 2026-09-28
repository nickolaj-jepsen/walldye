import { describe, expect, it } from 'vitest';
import { normaliseSearch } from '../../src/lib/content';
import { countFor, matches, ordered, parseQuery, serialiseQuery, type Filterable } from '../../src/scripts/filter';

const item = (slug: string, title: string, added: string, facets: string[], search = title.toLowerCase()): Filterable => ({
  slug,
  title,
  added,
  facets: new Set(facets),
  search,
});

const ITEMS = [
  item('a', 'Zebra', '2026-01-01', ['technique:dither', 'subject:space']),
  item('b', 'apple', '2026-03-01', ['technique:drafting', 'subject:maps', 'other:any-screen']),
  item('c', 'Mango', '2026-03-01', ['technique:dither', 'subject:maps']),
  item('d', 'Éclair', '2026-02-01', ['technique:glyph'], 'eclair by georg nees'),
];

describe('parseQuery / serialiseQuery', () => {
  it('reads the form serialisation and drops unknown values', () => {
    const s = parseQuery(new URLSearchParams('q=moon&sort=title&technique=dither&technique=bogus&subject=maps&t=nord'), (_facet, v) => v !== 'bogus');
    expect(s.q).toBe('moon');
    expect(s.sort).toBe('title');
    expect([...s.facets.get('technique')!]).toEqual(['dither']);
    expect([...s.facets.get('subject')!]).toEqual(['maps']);
    expect(s.facets.has('t')).toBe(false);
  });

  it('treats any other sort as newest and leaves defaults out', () => {
    const s = parseQuery(new URLSearchParams('sort=oldest&q=%20%20'));
    expect(s.sort).toBe('newest');
    expect(serialiseQuery(s)).toBe('');
  });

  it('writes facet values in the order given', () => {
    const s = parseQuery(new URLSearchParams('subject=maps&technique=drafting&technique=dither'));
    expect(serialiseQuery(s)).toBe('technique=drafting&technique=dither&subject=maps');
    expect(serialiseQuery(s, [['technique', 'dither'], ['technique', 'drafting'], ['subject', 'maps'], ['subject', 'space']])).toBe(
      'technique=dither&technique=drafting&subject=maps',
    );
  });
});

describe('matches / countFor', () => {
  it('is OR within a facet and AND across facets', () => {
    const s = parseQuery(new URLSearchParams('technique=dither&technique=drafting&subject=maps'));
    expect(ITEMS.filter((it) => matches(it, s)).map((it) => it.slug)).toEqual(['b', 'c']);
  });

  it('searches the normalised text', () => {
    const s = parseQuery(new URLSearchParams('q=  GEORG   Nées '));
    expect(ITEMS.filter((it) => matches(it, s)).map((it) => it.slug)).toEqual(['d']);
  });

  it('matches typewriter and typographer\'s apostrophes alike', () => {
    const baldur = item('e', 'Baldur’s Gate', '2026-02-01', [], normaliseSearch('Baldur’s Gate'));
    for (const q of ["baldur's", 'Baldur’s gate']) {
      expect(matches(baldur, parseQuery(new URLSearchParams({ q })))).toBe(true);
    }
  });

  it('counts a box against the other facets only', () => {
    const s = parseQuery(new URLSearchParams('technique=dither&subject=maps'));
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
});
