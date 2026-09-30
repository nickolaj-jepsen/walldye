import { describe, expect, it } from 'vitest';
import {
  aspectOfLabel,
  defaultSort,
  filterGroups,
  type Piece,
  relatedPieces,
} from '../../src/lib/content';

const piece = (
  slug: string,
  facets: Partial<Pick<Piece, 'technique' | 'subject' | 'lineage'>> = {},
  added = '2026-01-01',
): Piece =>
  ({
    slug,
    title: slug,
    added,
    views: 0,
    recent: 0,
    technique: [],
    subject: [],
    lineage: [],
    sources: [],
    aspects: ['16:9'],
    hasScript: true,
    model: 'claude-opus-5-5',
    ...facets,
  }) as unknown as Piece;

describe('defaultSort', () => {
  it('is featured when any piece is, else popular once any piece has a view, else newest', () => {
    expect(defaultSort([{ views: 0 }, { views: 0 }])).toBe('newest');
    expect(defaultSort([{ views: 0 }, { views: 3 }])).toBe('popular');
    expect(defaultSort([{ views: 0 }, { views: 3, featured: 0 }])).toBe('featured');
    expect(defaultSort([])).toBe('newest');
  });
});

describe('aspectOfLabel', () => {
  it('reads a ?shape= value and rejects anything else', () => {
    expect(aspectOfLabel('9x19.5')).toBe('9:19.5');
    expect(aspectOfLabel('16x9')).toBe('16:9');
    expect(aspectOfLabel('4x3')).toBeUndefined();
    expect(aspectOfLabel(null)).toBeUndefined();
  });
});

describe('filterGroups', () => {
  it('leaves out entries that match more than nine in ten pieces', () => {
    const pieces = Array.from({ length: 20 }, (_, i) =>
      piece(`p${i}`, {
        technique: i < 19 ? ['dither'] : ['line'],
        subject: i < 18 ? ['maps'] : [],
      }),
    );
    const technique = filterGroups(pieces, () => undefined).find((g) => g.facet === 'technique');
    // dither matches 19 of 20, over the share; line matches 1.
    expect(technique?.entries.map((e) => e.value)).toEqual(['line']);
    const subject = filterGroups(pieces, () => undefined).find((g) => g.facet === 'subject');
    // maps matches exactly 18 of 20, nine in ten, so it stays.
    expect(subject?.entries.map((e) => [e.value, e.count])).toEqual([['maps', 18]]);
  });
});

describe('relatedPieces', () => {
  const p = piece('self', { technique: ['dither'], lineage: ['op-art'], subject: ['space'] });
  const pieces = [
    p,
    piece('subject-only', { subject: ['space'] }, '2026-05-01'),
    piece('technique', { technique: ['dither'] }),
    piece('both', { technique: ['dither'], lineage: ['op-art'] }),
    piece('nothing', { technique: ['line'] }),
    piece('technique-newer', { technique: ['dither'] }, '2026-02-01'),
  ];

  it('ranks by shared facets, technique and lineage over subject, then newest', () => {
    expect(relatedPieces(p, pieces, 10).map((q) => q.slug)).toEqual([
      'both',
      'technique-newer',
      'technique',
      'subject-only',
    ]);
  });

  it('leaves out the piece itself and pieces sharing nothing, and stops at n', () => {
    expect(relatedPieces(p, pieces, 2).map((q) => q.slug)).toEqual(['both', 'technique-newer']);
    expect(relatedPieces(piece('alone', { technique: ['glyph'] }), pieces, 4)).toEqual([]);
  });
});
