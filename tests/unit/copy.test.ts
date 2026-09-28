import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { loadMeta, slugs } from '../../src/lib/hash';
import { colourWords, lintCopy, sentences } from '../../src/lib/meta';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));

// Committed copy that breaks a rule, pending the owner's rewrite; delete an entry once its meta.yaml is fixed.
const KNOWN: Record<string, string[]> = {};

describe('copy lint (h)', () => {
  it.each(slugs(ROOT))('%s meta.yaml', (slug) => {
    expect(lintCopy(loadMeta(ROOT, slug))).toEqual(KNOWN[slug] ?? []);
  });

  it('flags colour words but not token names', () => {
    expect(colourWords('A terracotta disc on Grey ground, lit in ORANGE_DARK and BLUE.')).toEqual(['grey', 'terracotta']);
    expect(lintCopy({ title: 'Red moon' })).toEqual(['title: colour words red']);
    expect(lintCopy({ notes: 'Drawn in amber.' })).toEqual(['notes: colour words amber']);
    expect(colourWords('reddish Blueprint')).toEqual([]);
  });

  it('flags plural colour words', () => {
    expect(colourWords('Greys and whites under the ambers; GREYS, BLUES, crimsons')).toEqual([
      'ambers',
      'crimsons',
      'greys',
      'whites',
    ]);
  });

  it('limits descriptions to 30 words and two sentences', () => {
    const long = Array.from({ length: 31 }, () => 'dot').join(' ');
    expect(lintCopy({ description: long })).toEqual(['description: 31 words, over 30']);
    expect(lintCopy({ description: 'One line. Two lines. Three lines.' })).toEqual(['description: 3 sentences, over 2']);
    expect(lintCopy({ description: 'A lamp drawn as Fig. 1 of a patent. Only the filament is lit.' })).toEqual([]);
    expect([sentences('One. Two'), sentences('No stop'), sentences('Ends here.'), sentences('Ask? Yes!')]).toEqual([2, 1, 1, 2]);
  });

  it('flags evaluative adjectives, internal terms, licence names, machinery numbers and theme roles', () => {
    expect(lintCopy({ description: 'A stunning, timeless grid.' })).toEqual(['description: evaluative adjective "stunning"']);
    expect(lintCopy({ description: 'A grid that quietly delves into order.' })).toEqual(['description: stock phrase "quietly"']);
    expect(lintCopy({ notes: 'Each seed picks a preset.' })).toEqual(['notes: internal term "seed"']);
    expect(lintCopy({ notes: 'Released under CC0.' })).toEqual(['notes: licence identifier "CC0"']);
    expect(lintCopy({ notes: 'Within 2 RGB units.' })).toEqual(['notes: machinery number "RGB units"']);
    expect(lintCopy({ description: 'Squares 12px wide.' })).toEqual(['description: machinery number "12px"']);
    expect(lintCopy({ description: 'One square in the accent.' })).toEqual(['description: theme role as a noun "the accent"']);
    expect(lintCopy({ description: 'Square accent cells, one picked out.' })).toEqual([]);
  });
});
