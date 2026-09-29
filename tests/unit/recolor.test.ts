import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  entries,
  pickTemplate,
  prepareTemplate,
  recolor,
  type Slots,
  type SlotsEntry,
  select,
} from '../../src/lib/recolor';
import { normalizeSeeds, PRESETS, parseToken, type Seeds } from '../../src/lib/theme';
import { findColors, skeleton } from '../../src/lib/tokenize';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const read = (rel: string) => readFileSync(`${ROOT}${rel}`, 'utf8');
const slotsOf = (slug: string) => JSON.parse(read(`wallpapers/${slug}/build/slots.json`)) as Slots;
const seeds = (token: string) => parseToken(token) as Seeds;
const sha256 = (text: string) => createHash('sha256').update(text).digest('hex');

interface Manifest {
  themes: string[];
  pieces: Record<string, { design_sha: string }>;
  renders: {
    slug: string;
    aspect: string;
    theme: string;
    entry: string;
    template: string;
    sha256: string;
    render: string;
  }[];
  resvg: { svg: string };
}
const MANIFEST = JSON.parse(read('tests/fixtures/manifest.json')) as Manifest;
const REFERENCE_PIECES = Object.keys(MANIFEST.pieces);

/** Largest per-channel difference between the slot colors of two SVGs with the same skeleton. */
function maxSlotError(a: string, b: string): number {
  const ca = findColors(a).map((s) => s[2]);
  const cb = findColors(b).map((s) => s[2]);
  expect(ca.length).toBe(cb.length);
  let worst = 0;
  ca.forEach((x, i) => {
    for (let k = 1; k < 7; k += 2)
      worst = Math.max(
        worst,
        Math.abs(parseInt(x.slice(k, k + 2), 16) - parseInt(cb[i].slice(k, k + 2), 16)),
      );
  });
  return worst;
}

describe('fireproof passthrough (a)', () => {
  const templates = REFERENCE_PIECES.flatMap((slug) =>
    entries(slotsOf(slug)).map(([key, entry]) => ({ slug, key, entry })),
  );

  it.each(templates)('$slug $key is returned byte for byte', ({ slug, entry }) => {
    const template = read(`wallpapers/${slug}/build/${entry.file}`);
    expect(recolor(template, entry, PRESETS.fireproof)).toBe(template);
    expect(
      recolor(
        prepareTemplate(template),
        entry,
        normalizeSeeds({ bg: '#1c1b1a', fg: 'DAD8CE', accent: 'cf6a4c' }),
      ),
    ).toBe(template);
  });
});

describe('recolor matches the Python renders (b)', () => {
  it('uses fixtures made from the current builds', () => {
    for (const slug of REFERENCE_PIECES)
      expect(slotsOf(slug).design_sha, `${slug}: rerun tests/python/fixtures/regen.py`).toBe(
        MANIFEST.pieces[slug].design_sha,
      );
    expect(MANIFEST.themes).toHaveLength(4);
  });

  it.each(MANIFEST.renders)(
    '$slug $aspect under $theme',
    ({ slug, aspect, theme, entry: key, template: path, sha256: sha, render }) => {
      const template = read(path);
      expect(sha256(template), `${path} changed since the fixture was made`).toBe(sha);
      const picked = select(slotsOf(slug), aspect, seeds(theme));
      expect(picked.key).toBe(key);
      const out = recolor(template, picked.entry, seeds(theme));
      const want = read(render);
      expect(skeleton(out)).toBe(skeleton(want));
      expect(maxSlotError(out, want)).toBeLessThanOrEqual(2);
    },
  );

  it('is byte-equal to the Python reference recolor', () => {
    const [slug, aspect, theme] = ['schotter', '16:9', 'nord'];
    const picked = select(slotsOf(slug), aspect, seeds(theme));
    const out = recolor(
      read(`wallpapers/${slug}/build/${picked.entry.file}`),
      picked.entry,
      seeds(theme),
    );
    expect(out).toBe(read(MANIFEST.resvg.svg));
  });
});

describe('per-occurrence slots (f)', () => {
  const dir = 'src/lib/__fixtures__/collision/';
  const template = read(`${dir}16x9.svg`);
  const slots = JSON.parse(read(`${dir}slots.json`)) as Slots;
  const renders = JSON.parse(read(`${dir}renders.json`)) as Record<string, string>;
  const perHex = JSON.parse(read(`${dir}per-hex.json`)) as Omit<SlotsEntry, 'file' | 'sha256'>;

  it('has two roles on one fireproof hex', () => {
    const colors = findColors(template).map((s) => s[2]);
    expect(colors[1]).toBe(colors[2]);
  });

  it('recolors within 2 units with per-occurrence slots', () => {
    for (const [theme, want] of Object.entries(renders)) {
      const picked = select(slots, '16:9', seeds(theme));
      const out = recolor(template, picked.entry, seeds(theme));
      expect(skeleton(out)).toBe(skeleton(want));
      expect(maxSlotError(out, want), theme).toBeLessThanOrEqual(2);
    }
  });

  it('misses by more than 2 units with one slot per fireproof hex', () => {
    const entry: SlotsEntry = { file: '16x9.svg', sha256: '', ...perHex };
    const dark = Object.keys(renders).filter(
      (t) => select(slots, '16:9', seeds(t)).key === '16:9/dark',
    );
    const worst = Math.max(
      ...dark.map((t) => maxSlotError(recolor(template, entry, seeds(t)), renders[t])),
    );
    expect(worst).toBeGreaterThan(2);
  });
});

describe('template choice', () => {
  const entry = (file: string, n = 1): SlotsEntry => ({
    file,
    sha256: '',
    n,
    coefs: [[1, 0, 0, 0, 0, 0]],
    occ: [0],
  });
  const both = {
    '16:9/dark': entry('16x9.svg'),
    '16:9/light': entry('16x9.light.svg'),
  } as unknown as Slots;

  it("picks the entry of the seeds' regime", () => {
    expect(pickTemplate(both, '16:9', 'light')).toMatchObject({ key: '16:9/light' });
    expect(pickTemplate(both, '16:9', 'dark')).toMatchObject({ key: '16:9/dark' });
    expect(select(both, '16:9', PRESETS['flexoki-light']).key).toBe('16:9/light');
    expect(select(both, '16:9', PRESETS.nord).key).toBe('16:9/dark');
    expect(() => pickTemplate(both, '21:9', 'dark')).toThrow('no 21:9/dark entry');
    expect(() =>
      pickTemplate({ '16:9/dark': entry('16x9.svg') } as unknown as Slots, '16:9', 'light'),
    ).toThrow('no 16:9/light entry');
  });

  it('falls back to the template when the slot count does not match', () => {
    const template = '<svg><rect fill="#1C1B1A"/></svg>';
    expect(recolor(template, entry('16x9.svg', 2), PRESETS.nord)).toBe(template);
    expect(recolor(template, { ...entry('16x9.svg'), occ: [3] }, PRESETS.nord)).toBe(template);
    expect(recolor(template, entry('16x9.svg'), PRESETS.nord)).toBe(
      '<svg><rect fill="#2E3440"/></svg>',
    );
  });

  it('rounds half to even and clamps', () => {
    const template = '<svg><rect fill="#000"/><rect fill="#000"/></svg>';
    const e: SlotsEntry = {
      file: '',
      sha256: '',
      n: 2,
      coefs: [
        [0, 0, 0, 66.5, 67.5, -3],
        [2, 0, 0, 0, 0, 300],
      ],
      occ: [0, 1],
    };
    expect(
      recolor(template, e, normalizeSeeds({ bg: '#808080', fg: '#000000', accent: '#000000' })),
    ).toBe('<svg><rect fill="#424400"/><rect fill="#FFFFFF"/></svg>');
  });
});

describe("the reference pieces' templates", () => {
  it('have as many slots as slots.json says', () => {
    for (const slug of REFERENCE_PIECES) {
      for (const [key, e] of entries(slotsOf(slug))) {
        expect(
          findColors(read(`wallpapers/${slug}/build/${e.file}`)).length,
          `${slug} ${key}`,
        ).toBe(e.n);
      }
    }
  });
});
