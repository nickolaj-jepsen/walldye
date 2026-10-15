/**
 * Server wrapper for the detail page: loads the bake rows of every template the piece can export
 * (a few KB) and provides them to the export panel inside it.
 */
import type { ReactNode } from 'react';
import type { Piece } from '../../lib/catalog';
import { getRows } from '../../server/catalog';
import { ExportRowsProvider } from './export-rows';
import { exportHashes } from './job';

export async function ExportRows({ piece, children }: { piece: Piece; children: ReactNode }) {
  return (
    <ExportRowsProvider rows={await getRows(exportHashes(piece))}>{children}</ExportRowsProvider>
  );
}
