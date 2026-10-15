'use client';
/**
 * The Colors section: the applied theme's three seeds, Change (which opens the picker) and Copy
 * link, the page's address with the theme in it.
 */
import type { CSSProperties } from 'react';
import { useTheme } from '../../client/theme/use-theme';
import { DEFAULT_PRESET } from '../../lib/presets';
import { CopyLink } from '../picker/CopyLink';

const ROWS = [
  { seed: 'bg', role: 'background' },
  { seed: 'fg', role: 'foreground' },
  { seed: 'accent', role: 'accent' },
] as const;

export function Colors() {
  const seeds = useTheme()?.seeds ?? DEFAULT_PRESET;
  return (
    <section aria-labelledby="theme-h">
      <h2 id="theme-h" className="sc">
        Colors
      </h2>
      <ul className="seedlist">
        {ROWS.map((r) => (
          <li key={r.seed}>
            <span className="chip" style={{ '--c': `var(--seed-${r.seed})` } as CSSProperties} />
            <span className="mono" data-seed={r.seed}>
              {seeds[r.seed]}
            </span>
            <span className="role">{r.role}</span>
          </li>
        ))}
      </ul>
      <p className="actions">
        <button type="button" className="textbtn" popoverTarget="picker">
          Change
        </button>
        <CopyLink />
      </p>
    </section>
  );
}
