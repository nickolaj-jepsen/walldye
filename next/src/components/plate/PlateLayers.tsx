'use client';
/**
 * The picture inside a plate's `<svg>`: the template's base and, for a piece with a motif, the motif
 * placed by a transform. Colors come from the seed variables on `:root`, so a theme change needs no
 * render. A template with `<defs>` is fetched and inlined (same-document `<use>`); any other is an
 * external `<use>` of /t/<hash>.svg. Failed loads are retried (template-text.ts). Where the regimes
 * have different files, only the applied regime's is drawn, and nothing before hydration, so the
 * other is never fetched.
 */
import type { CSSProperties, Ref } from 'react';
import { useRef, useState } from 'react';
import { useRegime } from '../../client/theme/use-theme';
import type { PlateData, ResolvedTemplate } from '../../lib/catalog';
import { partId, templateUrl } from '../../lib/catalog';
import { drawnPlacement, motifTransform, type Placement } from '../../lib/motif';
import { type LoadedTemplate, useTemplateFile } from './template-text';
import { useNear } from './use-near';

export interface PlateLayersProps {
  data: PlateData;
  /** Where the motif sits; null or absent leaves it where the design drew it. */
  placement?: Placement | null;
  /** Load only once the plate comes within a viewport of the view (grids). */
  lazy?: boolean;
  /** The motif's wrapper `<g>`, which a drag moves with a CSS transform before committing `placement`. */
  motifRef?: Ref<SVGGElement>;
  motifStyle?: CSSProperties;
}

interface Drawn {
  t: ResolvedTemplate;
  file: LoadedTemplate | undefined;
}

function href({ t, file }: Drawn, part: 'base' | 'motif'): string {
  const id = partId(t.hash, part);
  return t.inline ? `#${id}` : `${file?.url ?? templateUrl(t.hash)}#${id}`;
}

export function PlateLayers({
  data,
  placement,
  lazy = false,
  motifRef,
  motifStyle,
}: PlateLayersProps) {
  const ref = useRef<SVGGElement>(null);
  const regime = useRegime();
  const near = useNear(ref, lazy);
  const shared = data.dark.hash === data.light.hash;
  const t = shared ? data.dark : regime ? data[regime] : null;
  const shown = near ? t : null;
  const file = useTemplateFile(shown?.hash ?? null, shown?.inline ?? false);
  // An eager external template is drawn at once, before hydration too; the fetch beside it only
  // swaps in a retried address. Everything else waits for its file.
  const ready = shown && (file || (!shown.inline && !lazy)) ? shown : null;
  // The last template drawn stays up while the next one's file loads (a version or regime switch).
  const [held, setHeld] = useState<Drawn | null>(null);
  if (ready && (held?.t.hash !== ready.hash || held.file !== file)) setHeld({ t: ready, file });
  const drawn: Drawn | null = ready ? { t: ready, file } : shown ? held : null;
  const motif = drawn?.t.motif;
  return (
    <g ref={ref}>
      {drawn?.t.inline && drawn.file && (
        // biome-ignore lint/security/noDangerouslySetInnerHtml: the build's own template, served from /t/
        <defs dangerouslySetInnerHTML={{ __html: drawn.file.text }} />
      )}
      {drawn && <use href={href(drawn, 'base')} />}
      {drawn && motif && (
        <g ref={motifRef} style={motifStyle} data-motif-layer="">
          <g transform={motifTransform(placement ?? drawnPlacement(motif))}>
            <use href={href(drawn, 'motif')} />
          </g>
        </g>
      )}
    </g>
  );
}
