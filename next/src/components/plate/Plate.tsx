/**
 * A `.plate`: the box site.css sizes from `--ratio`, on the plate ground, holding the picture as an
 * `<svg>` whose viewBox is the part of the template shown (the whole canvas, or a crop of 16:9).
 * No hooks or server-only imports, so it renders on the server and inside client components alike;
 * the layers inside are a small client component. `motifRef` (a ref) only works from a client
 * parent. Children (the crop window, the motif frame) go after the picture.
 */
import { type CSSProperties, type ReactNode, type Ref, ViewTransition } from 'react';
import type { PlateData } from '../../lib/catalog';
import { num, type Placement } from '../../lib/motif';
import type { Box } from '../../lib/shape';
import { PlateLayers } from './PlateLayers';

export interface PlateProps {
  /** Names the plate for view transitions and tests. */
  slug: string;
  /** The templates to show: the shape's own, or 16:9's when `view` crops it. */
  data: PlateData;
  /** Accessible name of the picture: the version's alt text. */
  alt: string;
  /** The part of the canvas shown, in template units; the whole canvas when absent. */
  view?: Box;
  placement?: Placement | null;
  /** Grid plates: load once near the view. */
  lazy?: boolean;
  className?: string;
  style?: CSSProperties;
  motifRef?: Ref<SVGGElement>;
  motifStyle?: CSSProperties;
  /** A `<ViewTransition>` name: the same name on a grid plate and its page's plate morphs one into the other. */
  transitionName?: string;
  children?: ReactNode;
}

export function Plate({
  slug,
  data,
  alt,
  view,
  placement,
  lazy,
  className,
  style,
  motifRef,
  motifStyle,
  transitionName,
  children,
}: PlateProps) {
  const [w, h] = data.dark.canvas;
  const box = view ?? { x: 0, y: 0, w, h };
  const plate = (
    <div className={className ? `plate ${className}` : 'plate'} data-plate={slug} style={style}>
      <svg
        className="pic"
        viewBox={[box.x, box.y, box.w, box.h].map((v) => num(v)).join(' ')}
        role="img"
        aria-label={alt}
      >
        <PlateLayers
          data={data}
          placement={placement}
          lazy={lazy}
          motifRef={motifRef}
          motifStyle={motifStyle}
        />
      </svg>
      {children}
    </div>
  );
  // Only a named pair animates (class `plate` in site.css); a lone named plate stays still.
  return transitionName ? (
    <ViewTransition name={transitionName} share="plate" default="none">
      {plate}
    </ViewTransition>
  ) : (
    plate
  );
}
