/**
 * What a Download button makes: the format, then the size (an SVG's shape instead) and, for a raster
 * at the visitor's own screen size, "for your screen". Pure, so the Export panel's button can use it
 * too; summaryOf() gives its props and fileNameOf() the file's name for the detail state.
 */
import { downloadName } from '../../lib/content';
import styles from './Detail.module.css';
import type { Detail } from './detail-context';
import { sizePx } from './state';

export interface DownloadSummaryProps {
  /** The format's label, e.g. `PNG`. */
  format: string;
  /** `2560×1440`, or an SVG's shape such as `16:9`. */
  size: string;
  /** Whether the file is a raster at the screen's own size. */
  yours: boolean;
}

/** The summary of the file the detail state `d` would download. */
export function summaryOf(d: Pick<Detail, 'format' | 'size' | 'screenPx' | 'state'>) {
  const svg = d.format.value === 'svg';
  const [w, h] = sizePx(d.size, d.screenPx);
  return {
    format: d.format.label,
    size: svg ? d.state.aspect : `${w}×${h}`,
    yours: !svg && d.size === 'screen',
  } satisfies DownloadSummaryProps;
}

/** The file name the detail state `d` would download. */
export function fileNameOf(d: Detail): string {
  const [w, h] = sizePx(d.size, d.screenPx);
  return downloadName(
    d.piece.slug,
    d.version.name,
    d.token,
    d.format,
    `${w}x${h}`,
    d.state.aspect,
    !d.native,
  );
}

export function DownloadSummary({ format, size, yours }: DownloadSummaryProps) {
  return (
    <span className="file">
      {format}, <span className="mono">{size}</span>
      {yours && <span className={styles.yours}> for your screen</span>}
    </span>
  );
}
