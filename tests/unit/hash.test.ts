import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, describe, expect, it } from 'vitest';
import { compareCodePoints, designSha, digest, lockedVersions, parseMeta, sha256 } from '../../src/lib/hash';

interface Vector {
  name: string;
  /** Repo paths to file contents. */
  files: Record<string, string>;
  /** The hash lines that are not files. */
  lines: string[];
  /** The exact digested text. */
  text: string;
  sha256: string;
}

const FIXTURE = JSON.parse(readFileSync(fileURLToPath(new URL('../../src/lib/__fixtures__/hash-vector.json', import.meta.url)), 'utf8')) as {
  definition: string;
  vectors?: Vector[];
};
const VECTORS = (FIXTURE.vectors ?? []).map((v) => [v.name, v] as const);

const temps: string[] = [];
afterAll(() => {
  for (const dir of temps) rmSync(dir, { recursive: true, force: true });
});

/** A repo holding `v`'s files and a meta.yaml; the slug and the variant its lines name. */
function materialise(v: Vector): { root: string; slug: string; variant: string } {
  const root = mkdtempSync(join(tmpdir(), 'walldye-hash-'));
  temps.push(root);
  for (const [path, text] of Object.entries(v.files)) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    writeFileSync(join(root, path), text);
  }
  const slug = Object.keys(v.files)[0].split('/')[1];
  const field = (key: string) => v.lines.find((l) => l.startsWith(`${key}\t`))?.slice(key.length + 1);
  writeFileSync(join(root, 'wallpapers', slug, 'meta.yaml'), 'title: Example\n');
  return { root, slug, variant: field('variant') ?? 'default' };
}

describe('hash vectors shared with pytest (g)', () => {
  it('has the plain design and the variant with a data file', () => {
    expect(FIXTURE.vectors?.map((v) => v.name), 'src/lib/__fixtures__/hash-vector.json predates API v2: run tests/python/fixtures/regen.py').toEqual([
      'design',
      'variant-with-data',
    ]);
  });

  it.each(VECTORS)('%s digests its lines to the pinned sha256', (_, v) => {
    const lines = [...Object.entries(v.files).map(([path, text]) => `${path}\t${sha256(text)}`), ...v.lines];
    expect(digest(lines)).toBe(v.sha256);
    expect(sha256(v.text)).toBe(v.sha256);
    expect([...lines].sort(compareCodePoints).map((l) => `${l}\n`).join('')).toBe(v.text);
  });

  it.each(VECTORS)('%s is the design_sha of its files', (_, v) => {
    const { root, slug, variant } = materialise(v);
    expect(designSha(root, slug, variant)).toBe(v.sha256);
  });

  it('sorts by code point like Python', () => {
    expect(['b', 'a\uffff', 'a\u{1f600}', 'A'].sort(compareCodePoints)).toEqual(['A', 'a\uffff', 'a\u{1f600}', 'b']);
  });
});

describe('design_sha', () => {
  it('adds every file in data/ and, for a named variant only, a variant line', () => {
    const root = mkdtempSync(join(tmpdir(), 'walldye-hash-'));
    temps.push(root);
    const put = (path: string, text: string) => {
      mkdirSync(dirname(join(root, path)), { recursive: true });
      writeFileSync(join(root, path), text);
    };
    put('wallpapers/moon/design.py', 'x = 1\n');
    put('wallpapers/moon/meta.yaml', 'title: Moon\n');
    put('wallpapers/moon/data/b.npy', 'b');
    put('wallpapers/moon/data/a.json', '[]');
    mkdirSync(join(root, 'wallpapers/moon/data/nested'));
    const lines = [
      `wallpapers/moon/data/a.json\t${sha256('[]')}`,
      `wallpapers/moon/data/b.npy\t${sha256('b')}`,
      `wallpapers/moon/design.py\t${sha256('x = 1\n')}`,
    ];
    expect(designSha(root, 'moon')).toBe(digest(lines));
    expect(designSha(root, 'moon', 'default')).toBe(digest(lines));
    expect(designSha(root, 'moon', 'late')).toBe(digest([...lines, 'variant\tlate']));
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

  it('parses meta.yaml like PyYAML safe_load (YAML 1.1 booleans, repeated keys)', () => {
    expect(parseMeta('draft: yes\nai_generated: on\ntitle: a\ntitle: b')).toEqual({ draft: true, ai_generated: true, title: 'b' });
  });
});
