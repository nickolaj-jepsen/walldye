'use client';
/** The Source code appendix's render command for the version, shape, crop and placement the page shows. */
import { RunCommand } from '../source/RunCommand';
import { useDetail } from './detail-context';

export function LiveRunCommand() {
  const { piece, version, shape } = useDetail();
  return <RunCommand slug={piece.slug} variant={version.name} shape={shape} />;
}
