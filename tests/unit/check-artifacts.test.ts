import { execFileSync, spawnSync } from 'node:child_process';
import { appendFileSync, cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, describe, expect, it } from 'vitest';
import { checkArtifacts } from '../../scripts/check-artifacts';
import { renderLibSha, stampedRenderLibSha } from '../../src/lib/hash';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const COPIED = ['walldye', 'wallpapers', 'uv.lock', '.python-version', 'pyproject.toml'];
const temps: string[] = [];

/** A git repo holding the hash inputs and build output of this checkout; `track` stages walldye/ as CI's checkout has it. */
function copy(track = true): string {
  const dir = mkdtempSync(join(tmpdir(), 'walldye-artifacts-'));
  temps.push(dir);
  for (const name of COPIED) cpSync(join(ROOT, name), join(dir, name), { recursive: true, filter: (src) => !src.includes('__pycache__') });
  execFileSync('git', ['init', '-q'], { cwd: dir });
  if (track) execFileSync('git', ['add', 'walldye'], { cwd: dir });
  return dir;
}

function edit(dir: string, rel: string, change: (text: string) => string): void {
  const path = join(dir, rel);
  const before = readFileSync(path, 'utf8');
  const after = change(before);
  expect(after, `${rel} unchanged`).not.toBe(before);
  writeFileSync(path, after);
}

afterAll(() => {
  for (const dir of temps) rmSync(dir, { recursive: true, force: true });
});

describe('check-artifacts', () => {
  it('passes on this checkout', () => {
    expect(checkArtifacts(ROOT)).toEqual([]);
    expect(renderLibSha(ROOT)).toBe(stampedRenderLibSha(ROOT));
  });

  it('passes on a copy with walldye/ tracked, and with it untracked', () => {
    expect(checkArtifacts(copy(true))).toEqual([]);
    expect(checkArtifacts(copy(false))).toEqual([]);
  });

  it('fails when a design.py changes', () => {
    const dir = copy();
    appendFileSync(join(dir, 'wallpapers/schotter/design.py'), '# edited\n');
    expect(checkArtifacts(dir)).toEqual(['schotter: design_sha differs from the design and meta.yaml themes: run walldye build schotter']);
  });

  it('fails when meta.yaml changes the themes', () => {
    const dir = copy();
    appendFileSync(join(dir, 'wallpapers/radar-sweep/meta.yaml'), 'themes: [dark]\nnotes: Dark only.\n');
    expect(checkArtifacts(dir)).toEqual(['radar-sweep: design_sha differs from the design and meta.yaml themes: run walldye build radar-sweep']);
  });

  it('fails when a template is edited by hand', () => {
    const dir = copy();
    edit(dir, 'wallpapers/dither-moon/build/16x10.light.svg', (t) => t.replace('</svg>', '<rect/></svg>'));
    expect(checkArtifacts(dir)).toEqual([
      'dither-moon: build/16x10.light.svg does not match its sha256 in slots.json (edited by hand?): run walldye build dither-moon',
    ]);
  });

  it('fails when a template is missing or unlisted', () => {
    const dir = copy();
    rmSync(join(dir, 'wallpapers/radar-sweep/build/32x9.svg'));
    writeFileSync(join(dir, 'wallpapers/schotter/build/21x9.svg'), '<svg/>');
    expect(checkArtifacts(dir)).toEqual([
      'radar-sweep: build/32x9.svg (32:9/dark) is missing: run walldye build radar-sweep',
      'radar-sweep: build/32x9.svg (32:9/light) is missing: run walldye build radar-sweep',
      'schotter: build/21x9.svg is not in slots.json: run walldye build schotter',
    ]);
  });

  it('fails when a slot count disagrees with the template', () => {
    const dir = copy();
    edit(dir, 'wallpapers/schotter/build/slots.json', (t) => t.replace('"n":5,', '"n":6,'));
    expect(checkArtifacts(dir)).toContain('schotter: build/16x9.svg has 5 colour slots, slots.json says 6 for 16:9/dark');
  });

  it('fails when the render library changes, but not for walldye/tools or untracked files', () => {
    const dir = copy();
    appendFileSync(join(dir, 'walldye/tools/cli.py'), '# tooling is not a render input\n');
    writeFileSync(join(dir, 'walldye/scratch.py'), 'x = 1\n');
    expect(checkArtifacts(dir)).toEqual([]);
    execFileSync('git', ['add', 'walldye/scratch.py'], { cwd: dir });
    expect(checkArtifacts(dir)).toEqual([
      'the render inputs (walldye/, uv.lock, .python-version) changed since wallpapers/.render-lib.sha256: run walldye build --all',
    ]);
  });

  it('fails when _theme.py, a pinned dependency or the Python version changes', () => {
    for (const [rel, change] of [
      ['walldye/_theme.py', (t: string) => `${t}\n`],
      ['uv.lock', (t: string) => t.replace('name = "numpy"\nversion = "2.5.3"', 'name = "numpy"\nversion = "2.5.4"')],
      ['.python-version', () => '3.14\n'],
    ] as const) {
      const dir = copy();
      edit(dir, rel, change);
      expect(checkArtifacts(dir), rel).toEqual([
        'the render inputs (walldye/, uv.lock, .python-version) changed since wallpapers/.render-lib.sha256: run walldye build --all',
      ]);
    }
  });

  it('fails when slots.json was checked by another walldye version', () => {
    const dir = copy();
    edit(dir, 'wallpapers/schotter/build/slots.json', (t) => t.replace('"checked": "0.1.0"', '"checked": "0.0.9"'));
    expect(checkArtifacts(dir)).toEqual(['schotter: slots.json was checked by walldye "0.0.9", not 0.1.0: run walldye build schotter']);
  });

  it('fails when index.json disagrees with meta.yaml', () => {
    const dir = copy();
    edit(dir, 'wallpapers/schotter/meta.yaml', (t) => t.replace('title: Schotter, sideways', 'title: Schotter').replace('draft: false', 'draft: true'));
    edit(dir, 'wallpapers/radar-sweep/meta.yaml', (t) => t.replace('ai_generated: true', 'ai_generated: false\nlicense: CC-BY-4.0'));
    expect(checkArtifacts(dir)).toEqual([
      'wallpapers/index.json: radar-sweep license is "CC0-1.0", meta.yaml says "CC-BY-4.0": run walldye build radar-sweep',
      'wallpapers/index.json: schotter draft is false, meta.yaml says true: run walldye build schotter',
      'wallpapers/index.json: schotter title is "Schotter, sideways", meta.yaml says "Schotter": run walldye build schotter',
    ]);
  });

  it('fails when index.json lists the wrong pieces or aspects, or is laid out differently', () => {
    const dir = copy();
    const index = JSON.parse(readFileSync(join(dir, 'wallpapers/index.json'), 'utf8'));
    index['dither-moon'].aspects = ['16:9'];
    index.ghost = { aspects: ['16:9'], draft: false, license: 'CC0-1.0', title: 'Ghost' };
    writeFileSync(join(dir, 'wallpapers/index.json'), JSON.stringify(index, null, 2) + '\n');
    expect(checkArtifacts(dir)).toEqual([
      'wallpapers/index.json lists ghost, which has no meta.yaml: run walldye build',
      'wallpapers/index.json: dither-moon aspects is ["16:9"], slots.json says ["16:9","16:10","21:9","32:9","9:19.5","10:16"]: run walldye build dither-moon',
    ]);
    const other = copy();
    edit(other, 'wallpapers/index.json', (t) => JSON.stringify(JSON.parse(t)) + '\n');
    expect(checkArtifacts(other)).toEqual(['wallpapers/index.json is not laid out the way walldye build writes it: run walldye build']);
  });

  it('fails for an unbuilt piece', () => {
    const dir = copy();
    rmSync(join(dir, 'wallpapers/schotter/build'), { recursive: true });
    expect(checkArtifacts(dir)).toEqual(['schotter: not built (no build/slots.json): run walldye build schotter']);
  });

  it('exits 1 from the command line on a stale copy and 0 on a current one', () => {
    const tsx = join(ROOT, 'node_modules/.bin/tsx');
    const script = join(ROOT, 'scripts/check-artifacts.ts');
    const dir = copy();
    const ok = spawnSync(tsx, [script, dir], { encoding: 'utf8' });
    expect(ok.status, ok.stderr).toBe(0);
    expect(ok.stdout).toContain('3 pieces current');
    appendFileSync(join(dir, 'wallpapers/dither-moon/design.py'), '\n');
    const stale = spawnSync(tsx, [script, dir], { encoding: 'utf8' });
    expect(stale.status).toBe(1);
    expect(stale.stderr).toContain('dither-moon: design_sha differs');
    expect(stale.stderr).toContain('run walldye build dither-moon');
  });
});
