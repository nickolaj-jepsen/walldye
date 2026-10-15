'use client';
import { DownloadSummary, fileNameOf, summaryOf } from './DownloadSummary';
/**
 * The Download under the attribution, sharing the first screen with the plate: the Export panel's
 * file, made by the runner the panel registers in the detail state. Its title names the file.
 */
import { useDetail } from './detail-context';

export function QuickDownload() {
  const d = useDetail();
  const { busy, run } = d.download;
  return (
    <button
      type="button"
      className="download quick"
      id="quick-download"
      title={fileNameOf(d)}
      aria-busy={busy || undefined}
      onClick={(e) => run.current?.(e.currentTarget)}
    >
      <span className="k">{busy ? 'Preparing…' : 'Download'}</span>{' '}
      <DownloadSummary {...summaryOf(d)} />
    </button>
  );
}
