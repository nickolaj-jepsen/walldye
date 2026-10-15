'use client';
/**
 * The Export section: the Shape row, the motif's rows on wide screens, the Crop row, then the Export
 * panel (size, format, Download), which src/components/export/ owns.
 */
import { ExportPanel } from '../export/ExportPanel';
import { CropRow } from './CropRow';
import { useDetail } from './detail-context';
import { MotifRows } from './MotifRows';
import { ShapeRow } from './ShapeRow';

export function ExportSection() {
  const d = useDetail();
  return (
    <section id="export" aria-labelledby="export-h" data-license={d.piece.license}>
      <h2 id="export-h" className="sc">
        Export
      </h2>
      <ShapeRow />
      {d.piece.motif && !d.narrow && <MotifRows />}
      <CropRow />
      {/* EXPORT PANEL SLOT: the rest of the panel's state (templates, size, format, the Download runner) is in useDetail(). */}
      <ExportPanel
        slug={d.piece.slug}
        version={d.version.name}
        shape={d.state.aspect}
        crop={d.native ? null : d.shape.t}
        placement={d.placement}
      />
    </section>
  );
}
