/**
 * The custom properties plates read on `:root`: each seed's channels (0..255) and the regime
 * switches. The theme boot and applyTheme() set them; var templates (template-vars.ts) read them.
 */
import { hexToRgb, regimeOf, type Seeds } from './theme';

/** Seed channel custom properties in [bg, fg, accent] x [r, g, b] order. */
export const SEED_VARS = [
  ['--bg-r', '--bg-g', '--bg-b'],
  ['--fg-r', '--fg-g', '--fg-b'],
  ['--ac-r', '--ac-g', '--ac-b'],
] as const;

/** The regime switches: `--dk` is 1 in the dark regime and 0 in the light one, `--lt` the reverse. */
export const REGIME_VARS = { dark: '--dk', light: '--lt' } as const;

/** Custom property values for `:root`: the seed channels ("28") and the regime switches. */
export function seedVars(seeds: Seeds): Record<string, string> {
  const out: Record<string, string> = {};
  [seeds.bg, seeds.fg, seeds.accent].forEach((hex, s) => {
    hexToRgb(hex).forEach((v, ch) => {
      out[SEED_VARS[s][ch]] = String(v);
    });
  });
  const light = regimeOf(seeds) === 'light';
  out[REGIME_VARS.dark] = light ? '0' : '1';
  out[REGIME_VARS.light] = light ? '1' : '0';
  return out;
}
