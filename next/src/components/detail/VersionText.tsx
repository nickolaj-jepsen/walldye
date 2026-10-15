'use client';
/** The shown version's description, which a named variant may give its own. */
import { useDetail } from './detail-context';

export function VersionDescription() {
  return (
    <p className="desc" id="desc">
      {useDetail().version.description}
    </p>
  );
}
