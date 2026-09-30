import { describe, expect, it } from 'vitest';
import { downloadName, FORMATS, fileStem, type Piece, versionCount } from '../../src/lib/content';
import { namedVariants, variantsMeta } from '../../src/lib/meta';

/** "<path>: <message>" for each problem variantsMeta finds in `value`. */
function problems(value: unknown): string[] {
  const r = variantsMeta.safeParse(value);
  return r.success ? [] : r.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`);
}

describe('meta.yaml variants in the content schema', () => {
  it('takes the default plus up to four named variants with labels, descriptions and draft flags', () => {
    expect(
      problems({
        default: { label: 'Early in the turn' },
        late: { label: 'Late in the turn', description: 'The arm late in its sweep.' },
        'open-sea': { label: 'Open water', draft: true },
        a: { label: 'A' },
        b2: { label: 'B' },
      }),
    ).toEqual([]);
  });

  it('needs a default and at least one named variant, and at most four', () => {
    expect(problems({ late: { label: 'Late' } })).toEqual([
      ': needs a default entry, the label of the version design.py draws without a variant',
    ]);
    expect(problems({ default: { label: 'Early' } })).toEqual([
      ': lists no named variants; leave variants: out',
    ]);
    const five = Object.fromEntries(['a', 'b', 'c', 'd', 'e'].map((n) => [n, { label: n }]));
    expect(problems({ default: { label: 'Default' }, ...five })).toEqual([
      ': at most 4 named variants, got 5',
    ]);
  });

  it('rejects names that are not lowercase words joined by single hyphens, or longer than 24 characters', () => {
    const named = (name: string) =>
      problems({ default: { label: 'Early' }, [name]: { label: 'Late' } });
    for (const bad of ['Late', 'late--sweep', '-late', 'late_sweep', 'a'.repeat(25)]) {
      expect(named(bad), bad).toEqual([
        `${bad}: ${bad} is not a variant name: lowercase words joined by single hyphens, at most 24 characters`,
      ]);
    }
    expect(named('a'.repeat(24))).toEqual([]);
  });

  it('keeps description and draft to named variants', () => {
    expect(
      problems({
        default: { label: 'Early', description: 'Early.', draft: true },
        late: { label: 'Late' },
      }),
    ).toEqual([
      'default.description: the default version shows the piece description',
      'default.draft: the default version is a draft only with the piece',
    ]);
  });

  it('wants a label of one to four words, unique within the piece, and nothing else', () => {
    expect(problems({ default: { label: 'Early' }, late: {} })).toHaveLength(1);
    expect(problems({ default: { label: ' ' }, late: { label: 'Late' } })).toHaveLength(1);
    expect(
      problems({
        default: { label: 'Early in the turn' },
        late: { label: 'Late in the long turn' },
      }),
    ).toEqual(['late.label: label has 5 words, over 4']);
    expect(problems({ default: { label: 'Open water' }, late: { label: 'open water' } })).toEqual([
      'late.label: label repeats the label of default',
    ]);
    expect(
      problems({ default: { label: 'Early' }, late: { label: 'Late', seed: 11 } }),
    ).toHaveLength(1);
    expect(
      problems({ default: { label: 'Early' }, late: { label: 'Late', draft: 'yes' } }),
    ).toHaveLength(1);
  });
});

describe('namedVariants', () => {
  it('lists the named variants that are mappings, in file order, without validating them', () => {
    expect(
      namedVariants({
        variants: {
          late: { label: 'Late', draft: true },
          default: { label: 'Early' },
          odd: 'odd',
          'open-sea': { draft: 'yes' },
        },
      }),
    ).toEqual([
      { name: 'late', label: 'Late', description: undefined, draft: true },
      { name: 'open-sea', label: undefined, description: undefined, draft: false },
    ]);
    expect(namedVariants({})).toEqual([]);
    expect(namedVariants({ variants: ['late'] })).toEqual([]);
  });
});

describe('version names in files', () => {
  const png = FORMATS.find((f) => f.value === 'png')!;
  const svg = FORMATS.find((f) => f.value === 'svg')!;

  it('adds --<variant> after the slug for a named variant only', () => {
    expect(fileStem('radar-sweep', 'default')).toBe('radar-sweep');
    expect(fileStem('radar-sweep', 'open-sea')).toBe('radar-sweep--open-sea');
    expect(downloadName('radar-sweep', 'default', 'nord', png, '2560x1440', '16:9', false)).toBe(
      'radar-sweep-nord-2560x1440.png',
    );
    expect(downloadName('radar-sweep', 'late', 'nord', png, '2560x1440', '16:9', false)).toBe(
      'radar-sweep--late-nord-2560x1440.png',
    );
    expect(downloadName('radar-sweep', 'late', '1c1b1a-dad8ce-cf6a4c', svg, '', '21:9', true)).toBe(
      'radar-sweep--late-1c1b1a-dad8ce-cf6a4c-21x9-crop.svg',
    );
  });

  it('counts the versions the detail page offers, and the drafts among them (astro dev only)', () => {
    const piece = (versions: { name: string; draft: boolean }[]) =>
      ({ versions }) as unknown as Piece;
    expect(versionCount(piece([]))).toEqual({ versions: 1, drafts: 0 });
    const shown = [
      { name: 'default', draft: false },
      { name: 'late', draft: false },
    ];
    expect(versionCount(piece(shown))).toEqual({ versions: 2, drafts: 0 });
    expect(versionCount(piece([...shown, { name: 'open-sea', draft: true }]))).toEqual({
      versions: 3,
      drafts: 1,
    });
  });
});
