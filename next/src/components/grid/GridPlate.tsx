/**
 * One grid entry: a plate, then a tombstone caption of title, version count and attribution. No
 * hooks, so server components (See also) and the index's client grid both render it.
 */
import type { Route } from 'next';
import type { PlateData } from '../../lib/catalog';
import { captionSources, type Piece } from '../../lib/content';
import type { Box } from '../../lib/shape';
import { Attribution } from '../Attribution';
import { Plate } from '../plate/Plate';
import { IntentLink } from './IntentLink';

/** What an entry shows of a piece; a whole Piece will do. */
export type GridPiece = Pick<Piece, 'slug' | 'title' | 'alt' | 'sources'> & {
  versions: readonly { draft: boolean }[];
};

export interface GridPlateProps {
  piece: GridPiece;
  /** The templates shown: the default version's 16:9 (resolvePlate(piece.plates['16:9'])), or a shape's. */
  data: PlateData;
  /** The part of `data`'s canvas shown, for a 16:9 template cropped to another shape. */
  view?: Box;
  /** Where the entry leads; the piece's page by default. */
  href?: Route;
  /** The title's heading level: h2 on the index, h3 under a section heading. */
  heading?: 'h2' | 'h3';
  /** Load the picture at once rather than when it nears the view: the first rows. */
  eager?: boolean;
  /** Left out by the index filter. */
  hidden?: boolean;
  transitionName?: string;
}

export function GridPlate({
  piece: p,
  data,
  view,
  href,
  heading: Heading = 'h2',
  eager = false,
  hidden,
  transitionName,
}: GridPlateProps) {
  const s = p.slug;
  const attributed = Boolean(captionSources(p));
  // As versionCount(): the default counts even without named variants.
  const versions = Math.max(1, p.versions.length);
  const drafts = p.versions.filter((v) => v.draft).length;
  const described = [versions > 1 && `v-${s}`, attributed && `a-${s}`].filter(Boolean).join(' ');
  return (
    <li data-slug={s} hidden={hidden}>
      <IntentLink
        href={href ?? (`/${s}` as Route)}
        aria-labelledby={`t-${s}`}
        aria-describedby={described || undefined}
      >
        <figure>
          <Plate
            slug={s}
            data={data}
            view={view}
            alt={p.alt}
            lazy={!eager}
            transitionName={transitionName}
          />
          <figcaption className="label-s">
            <Heading className="t" id={`t-${s}`}>
              {p.title}
            </Heading>
            {versions > 1 && (
              <span className="v lnum" id={`v-${s}`}>
                {versions} versions{drafts > 0 && ` (${drafts} draft)`}
              </span>
            )}
            {attributed && (
              <span className="a" id={`a-${s}`}>
                <Attribution piece={p} />
              </span>
            )}
          </figcaption>
        </figure>
      </IntentLink>
    </li>
  );
}
