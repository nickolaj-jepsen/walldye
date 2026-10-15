import { describe, expect, it } from 'vitest';
import type { Piece, PlateRef } from '../../lib/catalog';
import { exportHashes, rowsOf } from './job';

const ref = (dark: string, light = dark): PlateRef => ({ dark, light });

describe('exportHashes', () => {
  it('takes every version, shape and regime once', () => {
    const piece = {
      plates: { '16:9': ref('a') },
      versions: [
        { name: 'default', plates: { '16:9': ref('a'), '9:19.5': ref('b', 'c') } },
        { name: 'wide', plates: { '16:9': ref('d'), '21:9': ref('a') } },
      ],
    } as unknown as Piece;
    expect(exportHashes(piece).sort()).toEqual(['a', 'b', 'c', 'd']);
  });

  it('reads the default plates of a piece without named versions', () => {
    const piece = { plates: { '16:9': ref('a', 'b') }, versions: [], focus: [0.5, 0.5] };
    expect(exportHashes(piece as unknown as Piece).sort()).toEqual(['a', 'b']);
  });
});

describe('rowsOf', () => {
  it('throws for a template the page has no rows for', () => {
    const rows = { a: { vars: [], coefs: {} } };
    expect(rowsOf(rows, 'a')).toBe(rows.a);
    expect(() => rowsOf(rows, 'b')).toThrow(/no export rows/);
  });
});
