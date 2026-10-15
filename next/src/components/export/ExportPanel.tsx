'use client';
/**
 * The Export section's own rows: Size, Format, Download and the error line. It registers the runner
 * the Download under the attribution calls, and once the panel or that button is seen it starts
 * loading the rasterizer and checks whether WebP can be made.
 */
import { useEffect, useRef, useState } from 'react';
import { useTheme } from '../../client/theme/use-theme';
import { type Aspect, EXPORT_SIZES, FORMATS } from '../../lib/content';
import type { Placement } from '../../lib/motif';
import type { ExportShape } from '../../lib/shape';
import { DEFAULT_THEME, PRESETS } from '../../lib/theme';
import { DownloadSummary, fileNameOf, summaryOf } from '../detail/DownloadSummary';
import { useDetail } from '../detail/detail-context';
import { sizePx } from '../detail/state';
import styles from './export.module.css';
import { useExportRows } from './export-rows';
import type { ExportJob } from './job';
import { makeExport } from './make';
import { canEncodeWebp, prefetchRasterizer } from './rasterize';

export interface ExportPanelProps {
  slug: string;
  /** `default` or the variant name. */
  version: string;
  shape: Aspect;
  /** The crop position of a shape cut from 16:9; null for a shape the piece composes for. */
  crop: number | null;
  /** The motif's clamped placement; null leaves it where the design drew it. */
  placement: Placement | null;
}

export function ExportPanel({ slug, version, shape, crop, placement }: ExportPanelProps) {
  const d = useDetail();
  const rows = useExportRows();
  const theme = useTheme();
  const [webp, setWebp] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  // Busy state lags a render behind a double click; the ref does not.
  const running = useRef(false);
  const errorRef = useRef<HTMLSpanElement>(null);
  const { busy, setBusy, run } = d.download;
  const [w, h] = sizePx(d.size, d.screenPx);
  const name = fileNameOf(d);

  const job = (): ExportJob => {
    const exportShape: ExportShape = {
      aspect: shape,
      native: crop === null,
      t: crop ?? 0.5,
      place: placement,
    };
    return {
      slug,
      title: d.piece.title,
      license: d.piece.license,
      variant: version,
      plate: d.data,
      shape: exportShape,
      size: [w, h],
      format: d.format,
      // Before hydration the theme is unknown; the page is drawn in the default one.
      seeds: theme?.seeds ?? { ...PRESETS[DEFAULT_THEME] },
      token: d.token,
      name,
    };
  };

  /** Makes and saves the file; a failure writes the error and, from outside the panel, scrolls it into view. */
  const start = async (from: HTMLElement) => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setError('');
    try {
      await makeExport(job(), rows);
    } catch {
      setError('The file could not be made.');
      const panel = errorRef.current?.closest('#export');
      if (!panel?.contains(from)) errorRef.current?.scrollIntoView({ block: 'center' });
    } finally {
      running.current = false;
      setBusy(false);
    }
  };

  useEffect(() => {
    run.current = (from) => void start(from);
    return () => {
      run.current = null;
    };
  });

  const { chooseFormat } = d;
  useEffect(() => {
    const panel = errorRef.current?.closest('#export');
    const quick = document.getElementById('quick-download');
    const seen = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      seen.disconnect();
      prefetchRasterizer();
      void canEncodeWebp().then(setWebp);
    });
    for (const el of [panel, quick]) if (el) seen.observe(el);
    return () => seen.disconnect();
  }, []);

  const noWebp = webp === false;
  useEffect(() => {
    if (noWebp && d.format.value === 'webp') chooseFormat(FORMATS[1]);
  }, [noWebp, d.format.value, chooseFormat]);

  const offered = [...EXPORT_SIZES[d.state.aspect], 'screen'];
  const limited = offered.some((s) => !d.allowed(s));

  return (
    <>
      <div className="row">
        <span className="k">Size</span>
        <div className={`seg ${styles.seg}`} id="sizes" role="radiogroup" aria-label="Size">
          {offered.map((value) => {
            const ok = d.allowed(value);
            return (
              <label key={value}>
                <input
                  type="radio"
                  name="size"
                  value={value}
                  checked={value === d.size}
                  disabled={!ok}
                  aria-describedby={ok ? undefined : 'size-limit'}
                  onChange={() => d.chooseSize(value)}
                />
                <span>
                  {value === 'screen' ? (
                    'your screen'
                  ) : (
                    <span className="mono">{value.replace('x', '×')}</span>
                  )}
                </span>
              </label>
            );
          })}
        </div>
        <span className="sub hint" id="size-limit" hidden={!limited}>
          This browser can’t draw a file that large.
        </span>
      </div>
      <div className="row">
        <span className="k">Format</span>
        <div className={`seg ${styles.seg}`} role="radiogroup" aria-label="Format">
          {FORMATS.map((f) => {
            const off = f.value === 'webp' && noWebp;
            return (
              <label key={f.value}>
                <input
                  type="radio"
                  name="fmt"
                  value={f.value}
                  checked={d.format.value === f.value}
                  disabled={off}
                  aria-describedby={off ? 'format-hint' : undefined}
                  onChange={() => chooseFormat(f)}
                />
                <span>{f.label}</span>
              </label>
            );
          })}
        </div>
        <span className="sub hint" id="format-hint" hidden={!noWebp}>
          This browser can’t make WebP files.
        </span>
      </div>
      <button
        type="button"
        className="download row"
        id="download"
        title={name}
        aria-busy={busy || undefined}
        onClick={(e) => void start(e.currentTarget)}
      >
        <span className="k">{busy ? 'Preparing…' : 'Download'}</span>
        <DownloadSummary {...summaryOf(d)} />
      </button>
      <p className="row" aria-live="polite">
        <span ref={errorRef} className="sub msg err" id="export-error">
          {error}
        </span>
      </p>
    </>
  );
}
