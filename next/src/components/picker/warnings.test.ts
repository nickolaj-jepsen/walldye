import { describe, expect, it } from 'vitest';
import { PRESETS } from '../../lib/theme';
import { warningsFor } from './warnings';

describe('warningsFor', () => {
  it('raises nothing for a preset', () => {
    const { bg, fg, accent } = PRESETS.fireproof;
    expect(warningsFor({ bg, fg, accent })).toEqual({ faint: false, nearBg: false, nearFg: false });
  });

  it('warns when bg and fg are too close', () => {
    expect(warningsFor({ bg: '#202020', fg: '#303030', accent: '#FF0000' }).faint).toBe(true);
  });

  it('prefers the bg warning when the accent is near both', () => {
    const w = warningsFor({ bg: '#808080', fg: '#828282', accent: '#818181' });
    expect(w).toMatchObject({ nearBg: true, nearFg: false });
  });

  it('warns when the accent is near fg', () => {
    expect(warningsFor({ bg: '#000000', fg: '#FFFFFF', accent: '#FEFEFE' }).nearFg).toBe(true);
  });

  it('ignores fields without a valid color', () => {
    expect(warningsFor({ bg: '#20', fg: '#202020', accent: '' })).toEqual({
      faint: false,
      nearBg: false,
      nearFg: false,
    });
  });
});
