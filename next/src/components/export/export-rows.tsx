'use client';
/** The bake rows of a piece's templates, handed from the server to the export panel. */
import { createContext, type ReactNode, use } from 'react';
import type { BakeRows } from '../../lib/template-vars';

type Rows = Readonly<Record<string, BakeRows>>;

const RowsContext = createContext<Rows | null>(null);

/** Gives the export panel below it `rows`, by template hash. */
export function ExportRowsProvider({ rows, children }: { rows: Rows; children: ReactNode }) {
  return <RowsContext value={rows}>{children}</RowsContext>;
}

/** The rows of the enclosing ExportRows; throws outside one. */
export function useExportRows(): Rows {
  const rows = use(RowsContext);
  if (!rows) throw new Error('the export panel needs <ExportRows> around it');
  return rows;
}
