import { describe, expect, it } from 'vitest';
import { pressedOf } from './use-choice';

describe('pressedOf', () => {
  it('presses a fixed theme by token', () => {
    expect(pressedOf({ token: 'nord' })).toEqual({ preset: 'nord', family: null });
  });

  it('presses the family whose pair it is', () => {
    expect(pressedOf({ pair: ['gruvbox-dark', 'gruvbox-light'] })).toEqual({
      preset: null,
      family: 'gruvbox',
    });
  });

  it('presses nothing for a pair no family has', () => {
    expect(pressedOf({ pair: ['nord', 'gruvbox-light'] })).toEqual({ preset: null, family: null });
  });
});
