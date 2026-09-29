import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { captionParts, type Source } from '../../src/lib/content';
import {
  colorWords,
  licenseOf,
  lintCopy,
  sentences,
  smartQuotes,
  typesetMeta,
} from '../../src/lib/meta';
import { loadMeta, slugs } from '../catalog';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));

// Committed copy that breaks a rule, pending the owner's rewrite; delete an entry once its meta.yaml is fixed.
const KNOWN: Record<string, string[]> = {};

describe('copy lint (h)', () => {
  it.each(slugs(ROOT))('%s meta.yaml', (slug) => {
    expect(lintCopy(loadMeta(ROOT, slug))).toEqual(KNOWN[slug] ?? []);
  });

  it('flags color words but not token names', () => {
    expect(colorWords('A terracotta disc on Grey ground, lit in ORANGE_DARK and BLUE.')).toEqual([
      'grey',
      'terracotta',
    ]);
    expect(lintCopy({ title: 'Red moon' })).toEqual(['title: color words red']);
    expect(lintCopy({ notes: 'Drawn in amber.' })).toEqual(['notes: color words amber']);
    expect(colorWords('reddish Blueprint')).toEqual([]);
  });

  it('flags plural color words', () => {
    expect(colorWords('Greys and whites under the ambers; GREYS, BLUES, crimsons')).toEqual([
      'ambers',
      'crimsons',
      'greys',
      'whites',
    ]);
  });

  it('limits descriptions to 30 words and two sentences', () => {
    const long = Array.from({ length: 31 }, () => 'dot').join(' ');
    expect(lintCopy({ description: long })).toEqual(['description: 31 words, over 30']);
    expect(lintCopy({ description: 'One line. Two lines. Three lines.' })).toEqual([
      'description: 3 sentences, over 2',
    ]);
    expect(
      lintCopy({ description: 'A lamp drawn as Fig. 1 of a patent. Only the filament is lit.' }),
    ).toEqual([]);
    expect([
      sentences('One. Two'),
      sentences('No stop'),
      sentences('Ends here.'),
      sentences('Ask? Yes!'),
    ]).toEqual([2, 1, 1, 2]);
  });

  it('flags evaluative adjectives, internal terms, license names, machinery numbers and theme roles', () => {
    expect(lintCopy({ description: 'A stunning, timeless grid.' })).toEqual([
      'description: evaluative adjective "stunning"',
    ]);
    expect(lintCopy({ description: 'A grid that quietly delves into order.' })).toEqual([
      'description: stock phrase "quietly"',
    ]);
    expect(lintCopy({ notes: 'Each seed picks a preset.' })).toEqual([
      'notes: internal term "seed"',
    ]);
    expect(lintCopy({ notes: 'Released under CC0.' })).toEqual(['notes: license identifier "CC0"']);
    expect(lintCopy({ notes: 'Within 2 RGB units.' })).toEqual([
      'notes: machinery number "RGB units"',
    ]);
    expect(lintCopy({ description: 'Squares 12px wide.' })).toEqual([
      'description: machinery number "12px"',
    ]);
    expect(lintCopy({ description: 'One square in the accent.' })).toEqual([
      'description: theme role as a noun "the accent"',
    ]);
    expect(lintCopy({ description: 'Square accent cells, one picked out.' })).toEqual([]);
  });
});

describe("typographer's quotes outside the notes", () => {
  it('curls apostrophes and quotes, and leaves primes after figures', () => {
    expect(smartQuotes("Pey'j's hovercraft on Jade's lighthouse")).toBe(
      'Pey’j’s hovercraft on Jade’s lighthouse',
    );
    expect(smartQuotes("The players' 'best' lap, the \"W\", the '90s")).toBe(
      'The players’ ‘best’ lap, the “W”, the ’90s',
    );
    expect(smartQuotes("Le Club de l'Ouest")).toBe('Le Club de l’Ouest');
    expect(smartQuotes("16½''' ETA 6497-1, 12\" wide")).toBe("16½''' ETA 6497-1, 12\" wide");
  });

  it('applies to titles, descriptions, variant copy, sources and the franchise, not notes', () => {
    const meta = {
      title: "Baldur's Gate from the harbor",
      description: "Wyrm's Rock at dusk.",
      notes: "Markdown's own.",
      sources: [{ kind: 'inspiration', title: "Mirror's Edge", author: 'DICE', year: 2008 }],
      franchise: { title: "Baldur's Gate 3", owner: 'Larian Studios' },
      variants: {
        default: { label: 'Harbor' },
        night: { label: "Night's end", description: "The keep's lamps.", draft: true },
      },
    };
    expect(typesetMeta(meta)).toEqual({
      ...meta,
      title: 'Baldur’s Gate from the harbor',
      description: 'Wyrm’s Rock at dusk.',
      sources: [{ kind: 'inspiration', title: 'Mirror’s Edge', author: 'DICE', year: 2008 }],
      franchise: { title: 'Baldur’s Gate 3', owner: 'Larian Studios' },
      variants: {
        default: { label: 'Harbor' },
        night: { label: 'Night’s end', description: 'The keep’s lamps.', draft: true },
      },
    });
    expect(meta.title).toBe("Baldur's Gate from the harbor");
  });
});

describe('caption attribution', () => {
  /** The caption as text, titles between asterisks where the page sets them in italics and topics bare. */
  const caption = (sources: Partial<Source>[]) => {
    const c = captionParts({ sources: sources as Source[] });
    return (
      c &&
      c.lead +
        c.parts
          .map((p) => `${p.before}${p.title ? `*${p.title}*` : ''}${p.topic ?? ''}${p.after}`)
          .join('')
    );
  };

  it('lists sources as "A, B and C", even when an author has an "and" of its own', () => {
    expect(
      caption([
        { kind: 'inspiration', author: 'NetHack DevTeam', title: 'NetHack' },
        { kind: 'inspiration', author: 'Michael Toy and Glenn Wichman', title: 'Rogue' },
        { kind: 'inspiration', author: 'Brian Walker', title: 'Brogue' },
      ]),
    ).toBe(
      'inspired by NetHack DevTeam, *NetHack*, Michael Toy and Glenn Wichman, *Rogue* and Brian Walker, *Brogue*',
    );
  });

  it('names an author once for consecutive works, and keeps years for recreations only', () => {
    expect(
      caption([
        { kind: 'recreation', author: 'Mark Rothko', title: 'No. 61', year: 1953 },
        { kind: 'recreation', author: 'Mark Rothko', title: 'Seagram murals', year: 1958 },
      ]),
    ).toBe('after Mark Rothko, *No. 61*, 1953 and *Seagram murals*, 1958');
    expect(
      caption([{ kind: 'inspiration', author: 'Georg Nees', title: 'Schotter', year: 1968 }]),
    ).toBe('inspired by Georg Nees, *Schotter*');
  });

  it('prefers recreations, drops missing fields and leaves out references and data', () => {
    expect(
      caption([
        { kind: 'inspiration', title: 'Uranometria' },
        { kind: 'recreation', author: 'eBoy' },
      ]),
    ).toBe('after eBoy');
    expect(
      caption([
        { kind: 'inspiration', title: 'The Thames Tunnel' },
        { kind: 'inspiration', author: 'ECM Records' },
      ]),
    ).toBe('inspired by *The Thames Tunnel* and ECM Records');
    expect(
      caption([
        { kind: 'reference', topic: 'Synthwave' },
        { kind: 'data', topic: 'd3-celestial' },
      ]),
    ).toBeUndefined();
  });

  it('sets a topic upright where a title would stand', () => {
    expect(
      caption([
        { kind: 'recreation', author: 'Thayer Williams', topic: 'Arch Linux logo', year: 2007 },
        { kind: 'recreation', author: 'Thayer Williams', title: 'Arch wallpaper' },
      ]),
    ).toBe('after Thayer Williams, Arch Linux logo, 2007 and *Arch wallpaper*');
  });
});

describe('licenseOf', () => {
  const made = { model: 'claude-opus-5-5' };
  it('reads license:, then franchise:, then the default for a piece a model made', () => {
    expect(licenseOf({ ...made, license: 'CC-BY-4.0' })).toBe('CC-BY-4.0');
    expect(
      licenseOf({ ...made, franchise: { title: 'Outer Wilds', owner: 'Mobius Digital' } }),
    ).toBe('LicenseRef-fan-work');
    expect(licenseOf(made)).toBe('CC0-1.0');
  });
  it('resolves nothing for a recreation or a human-made piece without license:', () => {
    expect(licenseOf({ ...made, sources: [{ kind: 'recreation', title: 'Schotter' }] })).toBeNull();
    expect(licenseOf({ author: 'A. Person' })).toBeNull();
  });
});
