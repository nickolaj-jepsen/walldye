'use client';
/**
 * "See also": the related pieces as grid plates in the page's shape. A piece without a template of
 * that shape shows its 16:9 one cropped around its focus, as an export would crop it, and each link
 * opens the piece in that shape.
 */
import type { Route } from 'next';
import type { CSSProperties } from 'react';
import { PHONE_QUERY } from '../../client/screen';
import type { PlateData } from '../../lib/catalog';
import { type Aspect, aspectLabel, CANVAS, type Piece } from '../../lib/content';
import { cropBox, focusPosition, nearestAspect } from '../../lib/shape';
import { type GridPiece, GridPlate } from '../grid/GridPlate';
import { useDetail } from './detail-context';
import { useMedia, useScreenPx } from './use-screen';

/** One related piece, as the server hands it over. */
export interface RelatedPiece extends GridPiece {
  focus: Piece['focus'];
  /** The default version's templates of each shape it composes for. */
  plates: Partial<Record<Aspect, PlateData>> & Record<'16:9', PlateData>;
}

export function SeeAlso({ pieces }: { pieces: RelatedPiece[] }) {
  const shape = useDetail().state.aspect;
  const phone = useMedia(PHONE_QUERY);
  const px = useScreenPx();
  // The shape a page opens in without ?shape=: the screen's on a phone, else 16:9.
  const home: Aspect = phone && px ? nearestAspect(...px) : '16:9';
  const [w, h] = CANVAS[shape];
  return (
    <section
      className="related"
      aria-labelledby="related-h"
      data-shape={shape}
      data-tall={h > w ? '' : undefined}
      style={{ '--shape-ratio': w / h } as CSSProperties}
    >
      <h2 id="related-h" className="sc hair-t">
        See also
      </h2>
      <ul className="grid">
        {pieces.map((p) => {
          const own = p.plates[shape];
          const href = shape === home ? `/${p.slug}` : `/${p.slug}?shape=${aspectLabel(shape)}`;
          return (
            <GridPlate
              key={p.slug}
              piece={p}
              data={own ?? p.plates['16:9']}
              view={own ? undefined : cropBox(shape, focusPosition(shape, p.focus))}
              href={href as Route}
              heading="h3"
            />
          );
        })}
      </ul>
    </section>
  );
}
