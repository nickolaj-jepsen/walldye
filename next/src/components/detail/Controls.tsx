/** The detail page's controls column: Versions (for a piece with named ones), Export and Colors. */
import { Colors } from './Colors';
import { ExportSection } from './ExportSection';
import { Versions } from './Versions';

export function Controls({ named }: { named: boolean }) {
  return (
    <section
      className="controls"
      aria-label={named ? 'Versions, export and colors' : 'Export and colors'}
    >
      {named && <Versions />}
      <ExportSection />
      <Colors />
    </section>
  );
}
