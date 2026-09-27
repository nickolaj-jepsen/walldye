import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { compareCodePoints, digest, lockedVersions, parseMeta, sha256, themes } from '../../src/lib/hash';

const VECTOR = JSON.parse(readFileSync(fileURLToPath(new URL('../../src/lib/__fixtures__/hash-vector.json', import.meta.url)), 'utf8')) as {
  files: Record<string, string>;
  lines: string[];
  text: string;
  sha256: string;
};

describe('hash vector shared with pytest (g)', () => {
  it('digests the vector lines to the pinned sha256', () => {
    const lines = [...Object.entries(VECTOR.files).map(([path, text]) => `${path}\t${sha256(text)}`), ...VECTOR.lines];
    expect(digest(lines)).toBe(VECTOR.sha256);
    expect(sha256(VECTOR.text)).toBe(VECTOR.sha256);
    expect([...lines].sort(compareCodePoints).map((l) => `${l}\n`).join('')).toBe(VECTOR.text);
  });

  it('sorts by code point like Python', () => {
    expect(['b', 'a￿', 'a\u{1f600}', 'A'].sort(compareCodePoints)).toEqual(['A', 'a￿', 'a\u{1f600}', 'b']);
  });
});

describe('hash inputs', () => {
  it('reads RENDER_DEPS pins from uv.lock, skipping sub-tables and other packages', () => {
    const lock = [
      'version = 1',
      '[options]',
      'name = "numpy"',
      '[[package]]',
      'name = "numpy"',
      'version = "2.5.3"',
      'source = { registry = "https://pypi.org/simple" }',
      '[package.metadata]',
      'version = "9.9.9"',
      '[[package]]',
      'name = "numpyx"',
      'version = "1.0"',
      '[[package]]',
      'name = "scipy"',
      'version = "1.18.1"',
      'dependencies = [',
      '    { name = "numpy" },',
      ']',
    ].join('\n');
    expect(lockedVersions(lock, ['numpy', 'scipy', 'shapely'])).toEqual([
      ['numpy', '2.5.3'],
      ['scipy', '1.18.1'],
    ]);
  });

  it('reads themes the way hashing.themes() does', () => {
    expect(themes({})).toEqual(['dark', 'light']);
    expect(themes({ themes: [] })).toEqual(['dark', 'light']);
    expect(themes({ themes: null })).toEqual(['dark', 'light']);
    expect(themes({ themes: ['dark'] })).toEqual(['dark']);
    expect(themes(parseMeta('themes: [light, dark]') as Record<string, unknown>)).toEqual(['light', 'dark']);
  });

  it('parses meta.yaml like PyYAML safe_load (YAML 1.1 booleans, repeated keys)', () => {
    expect(parseMeta('draft: yes\nai_generated: on\ntitle: a\ntitle: b')).toEqual({ draft: true, ai_generated: true, title: 'b' });
  });
});
