/** Three swatches (bg, fg, accent) as `.chips`; decorative, so hidden from assistive tech. */
import type { CSSProperties } from 'react';

export interface ChipsProps {
  /** CSS colors, e.g. `var(--seed-bg)` or `#1C1B1A`. */
  colors: readonly [string, string, string];
  className?: string;
}

export function Chips({ colors, className }: ChipsProps) {
  return (
    <span className={className ? `chips ${className}` : 'chips'} aria-hidden="true">
      {colors.map((c, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: always the same three slots
        <span key={i} className="chip" style={{ '--c': c } as CSSProperties} />
      ))}
    </span>
  );
}
