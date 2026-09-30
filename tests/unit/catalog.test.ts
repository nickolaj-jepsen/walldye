import { createHash } from 'node:crypto';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { typesetNotes } from '../../src/lib/typeset';
import { readBuild } from '../../src/server/catalog/build';
import { loadFeatured } from '../../src/server/catalog/files';

const sha = (text: string) => createHash('sha256').update(text).digest('hex');

/** A build directory holding `template` as 16x9.svg and a slots.json that records `recorded`. */
function buildDir(template: string, recorded = sha(template), key = '16:9/dark'): string {
  const dir = mkdtempSync(join(tmpdir(), 'walldye-build-'));
  writeFileSync(join(dir, '16x9.svg'), template);
  const entry = { file: '16x9.svg', sha256: recorded, n: 0, coefs: [], occ: [] };
  writeFileSync(join(dir, 'slots.json'), JSON.stringify({ focus: [0.25, 0.75], [key]: entry }));
  return dir;
}

describe('readBuild', () => {
  it('serves each template and the slots.json under their hashes', () => {
    const b = readBuild('p', buildDir('<svg/>'));
    const hash = sha('<svg/>').slice(0, 12);
    expect(b.templates['16:9/dark']).toMatchObject({
      file: '16x9.svg',
      hash,
      url: `/t/${hash}.svg`,
    });
    expect(b.slotsUrl).toBe(`/t/${b.slotsHash}.slots.json`);
    expect(b.focus).toEqual([0.25, 0.75]);
  });

  it('throws naming the file when the build is stale', () => {
    expect(() => readBuild('p', buildDir('<svg/>', sha('other')))).toThrow(
      /differs from slots.json: run walldye build p/,
    );
    expect(() => readBuild('p', buildDir('<svg/>', undefined, '16:9/light'))).toThrow(
      /has no 16:9\/dark template/,
    );
    expect(() => readBuild('p', mkdtempSync(join(tmpdir(), 'walldye-empty-')))).toThrow(
      /slots.json is missing/,
    );
  });
});

describe('loadFeatured', () => {
  const file = (text: string) => {
    const path = join(mkdtempSync(join(tmpdir(), 'walldye-featured-')), 'featured.yaml');
    writeFileSync(path, text);
    return path;
  };

  it('places each listed piece in order', () => {
    expect([...loadFeatured(['a', 'b', 'c'], file('- c\n- a\n'))]).toEqual([
      ['c', 0],
      ['a', 1],
    ]);
    expect(loadFeatured(['a'], '/no/such/featured.yaml').size).toBe(0);
  });

  it('rejects a missing folder, a repeat and anything but a list of slugs', () => {
    expect(() => loadFeatured(['a'], file('- b\n'))).toThrow(/b is not a folder/);
    expect(() => loadFeatured(['a'], file('- a\n- a\n'))).toThrow(/a is listed twice/);
    expect(() => loadFeatured(['a'], file('a: 1\n'))).toThrow(/must be a list of slugs/);
  });
});

describe('typesetNotes', () => {
  it('sets italics, acronyms and letter-like figures, leaving code alone', () => {
    expect(typesetNotes('<p><em>Apollo</em> by NASA on a Z64 at 5.5, 16 × 9</p>')).toBe(
      '<p><i>Apollo</i> by <abbr>NASA</abbr> on a <span class="lnum">Z64</span> at <span class="lnum">5.5</span>, <span class="lnum">16 × 9</span></p>',
    );
    expect(typesetNotes('<code>NASA 5.5</code> &amp; ESA')).toBe(
      '<code>NASA 5.5</code> &amp; <abbr>ESA</abbr>',
    );
  });
});
