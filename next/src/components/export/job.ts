/** What one export needs, and the pure rules around it. */
import { allVersions, type Piece, type PlateData } from '../../lib/catalog';
import type { FORMATS } from '../../lib/content';
import type { ExportShape } from '../../lib/shape';
import type { BakeRows } from '../../lib/template-vars';
import type { Seeds } from '../../lib/theme';

export type Format = (typeof FORMATS)[number];

/** Everything one Download makes its file from, read when it is pressed. */
export interface ExportJob {
  slug: string;
  /** The piece's title, the SVG download's `<title>`. */
  title: string;
  /** The resolved license id, named in the SVG download's `<desc>`. */
  license: string;
  /** `default` or the variant name. */
  variant: string;
  /** The templates the export reads: the shape's own, else 16:9 to crop. */
  plate: PlateData;
  /** Shape, crop and the motif placement, already clamped. */
  shape: ExportShape;
  /** Output pixels of a raster; an SVG keeps the shape's canvas size. */
  size: readonly [number, number];
  format: Format;
  seeds: Seeds;
  token: string;
  /** The file name to save as. */
  name: string;
}

/** Every template hash an export of `piece` can read: each version's, shape's and regime's, deduplicated. */
export function exportHashes(piece: Piece): string[] {
  const hashes = new Set<string>();
  for (const v of allVersions(piece))
    for (const ref of Object.values(v.plates)) {
      hashes.add(ref.dark);
      hashes.add(ref.light);
    }
  return [...hashes];
}

/** Rows for the template `hash`; throws when the page was not given them. */
export function rowsOf(rows: Readonly<Record<string, BakeRows>>, hash: string): BakeRows {
  const r = rows[hash];
  if (!r) throw new Error(`no export rows for template ${hash}`);
  return r;
}
