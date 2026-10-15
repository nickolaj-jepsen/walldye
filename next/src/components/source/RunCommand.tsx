'use client';
import { useThemeToken } from '../../client/theme/use-theme';
/**
 * The `walldye render` line of "Run it yourself", in the applied theme. The default theme stands in
 * until hydration, since only the browser knows the visitor's.
 */
import type { Aspect } from '../../lib/content';
import { DEFAULT_PRESET } from '../../lib/presets';
import { type ExportShape, renderCommand } from '../../lib/shape';

const WHOLE: ExportShape = { aspect: '16:9' satisfies Aspect, native: true, t: 0.5 };

export interface RunCommandProps {
  slug: string;
  /** The version shown (`?v=`); the default when omitted. */
  variant?: string;
  /** The shape, crop and motif placement shown; the whole 16:9 picture when omitted. */
  shape?: ExportShape;
}

export function RunCommand({ slug, variant = 'default', shape = WHOLE }: RunCommandProps) {
  const token = useThemeToken() ?? DEFAULT_PRESET.name;
  return (
    <span id="run-render" data-slug={slug}>
      {renderCommand(slug, variant, token, shape)}
    </span>
  );
}
