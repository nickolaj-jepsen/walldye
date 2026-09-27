import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { findColours, joinSlots, NAMED, normalise, skeleton, SKELETON_MARK, splitSlots, substitute } from '../../src/lib/tokenize';

const SPEC = JSON.parse(readFileSync(fileURLToPath(new URL('../../src/lib/__fixtures__/tokenize.json', import.meta.url)), 'utf8')) as {
  skeleton_mark: string;
  named: Record<string, string>;
  cases: { name: string; input: string; occurrences: [number, number, string][]; normalised: string; skeleton: string }[];
};

describe('tokenizer spec shared with pytest (e)', () => {
  it.each(SPEC.cases)('$name', ({ input, occurrences, normalised, skeleton: skel }) => {
    expect(/^[\x00-\x7f]*$/.test(input)).toBe(true);
    expect(findColours(input)).toEqual(occurrences);
    expect(normalise(input)).toBe(normalised);
    expect(skeleton(input)).toBe(skel);
    expect(normalise(normalised)).toBe(normalised);
    expect(skeleton(normalised)).toBe(skel);
  });

  it('shares the named colour table and skeleton mark', () => {
    expect(Object.fromEntries(NAMED)).toEqual(SPEC.named);
    expect(NAMED.size).toBe(148);
    expect(SKELETON_MARK).toBe(SPEC.skeleton_mark);
  });
});

describe('substitution', () => {
  it('replaces slot values in place', () => {
    const svg = '<rect fill="#fff" stroke=" red "/><path fill="none"/>';
    expect(substitute(svg, ['#000000', '#111111'])).toBe('<rect fill="#000000" stroke=" #111111 "/><path fill="none"/>');
    expect(() => substitute(svg, ['#000000'])).toThrow();
  });

  it('splits and joins around the slots', () => {
    const svg = '<style>.a{fill:#abc}</style><rect style="stroke:blue" color="#123456"/>';
    const parts = splitSlots(svg);
    expect(parts).toHaveLength(4);
    expect(joinSlots(parts, ['1', '2', '3'])).toBe('<style>.a{fill:1}</style><rect style="stroke:2" color="3"/>');
    expect(parts.join('')).toBe(svg.replace('#abc', '').replace('blue', '').replace('#123456', ''));
  });

  it('matches Python on attribute values with whitespace Python counts and JS does not', () => {
    // \x1c-\x1f are whitespace to Python's re; the value is still exactly one colour.
    expect(findColours('<rect fill="\x1f#abc\x1c"/>')).toEqual([[13, 17, '#AABBCC']]);
    // U+FEFF is \s in JS but not in Python.
    expect(findColours('<rect fill="﻿#abc"/>')).toEqual([]);
    // Python's \w covers non-ASCII letters in element names.
    expect(findColours('<réct fill="#abc"/>')).toEqual([[12, 16, '#AABBCC']]);
  });
});
