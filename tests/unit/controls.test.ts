import { describe, expect, it } from 'vitest';
import {
  DRAW_MAX,
  DRAW_MIN,
  dragValue,
  editsFromQuery,
  editsQuery,
  editsSuffix,
  fitRange,
  isEdited,
  isText,
  knobStep,
  noEdits,
  overrides,
  parseDraw,
  parseKnob,
  pickDraw,
  readout,
  setItems,
  shellWord,
  validText,
  type Knob,
} from '../../src/lib/controls';

const knob = (k: Partial<Knob> & Pick<Knob, 'name' | 'kind'>): Knob => ({ label: k.name, lo: null, hi: null, choices: null, unit: '', maxLen: null, drag: null, ...k });
const SWEEP = knob({ name: 'sweep', kind: 'float', lo: 0, hi: 360, unit: 'deg' });
const WAVE = knob({ name: 'wave', kind: 'float', lo: 0.1, hi: 0.95 });
const TIMES = knob({ name: 'times', kind: 'int', lo: 2, hi: 9 });
const SKY = knob({ name: 'sky', kind: 'str', choices: [{ value: 'cassiopeia', label: 'Cassiopeia' }, { value: 'orion', label: 'Orion' }] });
const MODE = knob({ name: 'mode', kind: 'int', choices: [{ value: 3, label: '3' }, { value: 5, label: '5' }] });
const RING = knob({ name: 'ring', kind: 'bool' });
const WORD = knob({ name: 'word', kind: 'str', maxLen: 12 });
const KNOBS = [SWEEP, WAVE, TIMES, SKY, MODE, RING, WORD];
const PARAMS = { sweep: 60, wave: 0.5, times: 2, sky: 'cassiopeia', mode: 3, ring: true, word: 'fireproof', seed: null };

describe('text knobs', () => {
  it('take 1 to maxLen printable ASCII characters', () => {
    expect(isText(WORD)).toBe(true);
    expect(isText(SKY)).toBe(false);
    expect(validText(WORD, 'hello, world')).toBe(true);
    for (const text of ['', 'thirteen char', 'naïve', 'tab\there']) expect(validText(WORD, text)).toBe(false);
    expect(parseKnob(WORD, 'hi there')).toBe('hi there');
    expect(parseKnob(WORD, '')).toBeUndefined();
  });

  it('go in the query as typed, in the command quoted, and in file names cut short', () => {
    const e = { draw: null, knobs: { word: "it's a long word" } };
    expect(editsQuery(e, KNOBS)).toEqual([['word', "it's a long word"]]);
    expect(setItems(e, KNOBS)).toEqual(["word=it's a long word"]);
    expect(shellWord("word=it's a long word")).toBe(`'word=it'\\''s a long word'`);
    expect(shellWord('sweep=200')).toBe('sweep=200');
    expect(editsSuffix(e, KNOBS)).toBe('-wordit_s_a_long_word');
    expect(editsSuffix({ draw: null, knobs: { word: 'abcdefghijklmnopq' } }, KNOBS)).toBe('-wordabcdefghijklmnop');
  });
});

describe('dragging', () => {
  it('spans the whole range across the picture, fitted to the slider', () => {
    expect(dragValue(SWEEP, 60, 0.25)).toBe(150);
    expect(dragValue(SWEEP, 60, -1)).toBe(0);
    expect(dragValue(TIMES, 2, 0.5)).toBe(6);
    expect(fitRange(WAVE, 0.4987)).toBe(0.5);
  });
});

describe('knobs', () => {
  it('steps ints by one and floats by about a hundredth of the range', () => {
    expect(knobStep(TIMES)).toBe(1);
    expect(knobStep(SWEEP)).toBe(2);
    expect(knobStep(WAVE)).toBeCloseTo(0.005);
  });

  it('reads out ints and angles only', () => {
    expect(readout(TIMES, 4)).toBe('4');
    expect(readout(SWEEP, 90)).toBe('90°');
    expect(readout(SWEEP, 90.25)).toBe('90.3°');
    expect(readout(WAVE, 0.5)).toBeNull();
    expect(readout(MODE, 3)).toBeNull();
  });

  it('parses query values by kind, clamping and snapping numbers and refusing the rest', () => {
    expect(parseKnob(SWEEP, '200')).toBe(200);
    expect(parseKnob(SWEEP, '201')).toBe(202);
    expect(parseKnob(SWEEP, '999')).toBe(360);
    expect(parseKnob(TIMES, '4.4')).toBe(4);
    expect(parseKnob(SKY, 'orion')).toBe('orion');
    expect(parseKnob(MODE, '5')).toBe(5);
    expect(parseKnob(RING, 'false')).toBe(false);
    for (const [k, text] of [[SWEEP, 'x'], [SWEEP, '1e3'], [SWEEP, ''], [SKY, 'vega'], [MODE, '4'], [RING, '0']] as const) {
      expect(parseKnob(k, text)).toBeUndefined();
    }
  });

  it('parses draw numbers of one to nine digits from DRAW_MIN', () => {
    expect(parseDraw('37')).toBe(37);
    for (const text of [null, '', '0', '-3', '3.5', '1234567890', 'x']) expect(parseDraw(text)).toBeUndefined();
  });
});

describe('edits', () => {
  it('reads only values that differ from the version, and draw only when a new draw changes it', () => {
    const q = new URLSearchParams('sweep=60&wave=0.8&sky=orion&draw=37&mode=9');
    expect(editsFromQuery(q, KNOBS, PARAMS, true)).toEqual({ draw: 37, knobs: { wave: 0.8, sky: 'orion' } });
    expect(editsFromQuery(q, KNOBS, PARAMS, false).draw).toBeNull();
    expect(editsFromQuery(new URLSearchParams('draw=3'), KNOBS, { ...PARAMS, seed: 3 }, true)).toEqual(noEdits());
  });

  it('writes the query, the --set items and the file suffix in knob order, draw last', () => {
    const e = { draw: 37, knobs: { sky: 'orion', sweep: 200 } };
    expect(editsQuery(e, KNOBS)).toEqual([['sweep', '200'], ['sky', 'orion'], ['draw', '37']]);
    expect(setItems(e, KNOBS)).toEqual(['sweep=200', 'sky=orion', 'seed=37']);
    expect(editsSuffix(e, KNOBS)).toBe('-sweep200-skyorion-draw37');
    expect(overrides(e)).toEqual({ sky: 'orion', sweep: 200, seed: 37 });
    expect(editsSuffix(noEdits(), KNOBS)).toBe('');
    expect(isEdited(noEdits())).toBe(false);
    expect(isEdited({ draw: null, knobs: { ring: false } })).toBe(true);
  });

  it('picks a draw number other than the current one', () => {
    const values = [0.5, 0.5, 0.9];
    expect(pickDraw(DRAW_MIN + Math.floor(0.5 * (DRAW_MAX - DRAW_MIN + 1)), () => values.shift()!)).toBe(DRAW_MIN + Math.floor(0.9 * (DRAW_MAX - DRAW_MIN + 1)));
    for (let i = 0; i < 100; i++) {
      const n = pickDraw(null);
      expect(n).toBeGreaterThanOrEqual(DRAW_MIN);
      expect(n).toBeLessThanOrEqual(DRAW_MAX);
    }
  });
});
