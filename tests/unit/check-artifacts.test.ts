import { execFileSync, spawnSync } from 'node:child_process';
import { appendFileSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterAll, describe, expect, it } from 'vitest';
import { checkArtifacts } from '../../scripts/check-artifacts';
import { aspectLabel } from '../../src/lib/content';
import { designLines, digest, renderLibSha, sha256, variantLines } from '../../src/lib/hash';
import { findColours } from '../../src/lib/tokenize';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
const VERSION = '0.2.0';
const temps: string[] = [];

const LOCK = ['numpy', 'scipy', 'shapely', 'scikit-image'].map((name, i) => `[[package]]\nname = "${name}"\nversion = "1.${i}.0"\n`).join('\n');

const RINGS_META = `title: Rings
description: Three rings around a point.
added: 2026-09-27
author: Claude Opus 5.5
ai_generated: true
themes: [dark]
draft: false
`;

const MOON_META = `title: Moon
description: A moon over a flat horizon.
added: 2026-09-28
author: Claude Opus 5.5
ai_generated: true
draft: false
variants:
  default: {label: Full moon}
  late: {label: Crescent, description: A crescent over a flat horizon.}
  open-sea: {label: New moon, draft: true}
`;

/** One template: a background and one disc whose place tells the versions and aspects apart. */
function svg(aspect: string, variant: string, shift: number): string {
  const [w, h] = aspect === '16:9' ? [1920, 1080] : [1080, 1728];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}"><rect width="${w}" height="${h}" fill="#1C1B1A"/><circle cx="${w / 2 + shift}" cy="${h / 2}" r="120" fill="#CF6A4C" data-v="${variant}"/></svg>\n`;
}

const write = (dir: string, rel: string, text: string) => {
  mkdirSync(dirname(join(dir, rel)), { recursive: true });
  writeFileSync(join(dir, rel), text);
};

/** Writes `variant`'s templates and slots.json into the piece's build directory, as `walldye build` would. */
function build(dir: string, slug: string, variant: string, aspects: string[], light: boolean, shift: number): void {
  const rel = variant === 'default' ? `wallpapers/${slug}/build` : `wallpapers/${slug}/build/${variant}`;
  const slots: Record<string, unknown> = { design_sha: digest(variantLines(designLines(dir, slug), variant)) };
  if (variant !== 'default') slots.variant = variant;
  Object.assign(slots, { focus: [0.5, 0.5], cells: [], probes: {}, checked: VERSION });
  for (const aspect of aspects) {
    const file = `${aspectLabel(aspect)}.svg`;
    const text = svg(aspect, variant, shift);
    write(dir, `${rel}/${file}`, text);
    const n = findColours(text).length;
    const entry = { file, sha256: sha256(text), n, coefs: [[1, 0, 0, 0, 0, 0]], occ: Array(n).fill(0) };
    slots[`${aspect}/dark`] = entry;
    if (light) slots[`${aspect}/light`] = entry;
  }
  write(dir, `${rel}/slots.json`, `${JSON.stringify(slots)}\n`);
}

const INDEX = {
  moon: {
    aspects: ['16:9', '10:16'],
    draft: false,
    license: 'CC0-1.0',
    title: 'Moon',
    variants: { late: { draft: false, label: 'Crescent' }, 'open-sea': { draft: true, label: 'New moon' } },
  },
  rings: { aspects: ['16:9'], draft: false, license: 'CC0-1.0', title: 'Rings', variants: {} },
};

/**
 * A git repo whose committed artifacts are current: `rings`, one version at 16:9 for dark themes,
 * and `moon`, with a data file and two named variants at 16:9 and 10:16. `track` stages walldye/ as
 * CI's checkout has it.
 */
function repo(track = true): string {
  const dir = mkdtempSync(join(tmpdir(), 'walldye-artifacts-'));
  temps.push(dir);
  write(dir, 'pyproject.toml', `[project]\nname = "walldye"\nversion = "${VERSION}"\n`);
  write(dir, 'uv.lock', LOCK);
  write(dir, '.python-version', '3.13\n');
  write(dir, 'walldye/__init__.py', '"""Library."""\n');
  write(dir, 'walldye/_theme.py', 'PRESETS = {}\n');
  write(dir, 'walldye/tools/cli.py', '"""CLI."""\n');
  write(dir, 'wallpapers/rings/design.py', '"""Rings."""\n');
  write(dir, 'wallpapers/rings/meta.yaml', RINGS_META);
  write(dir, 'wallpapers/moon/design.py', '"""Moon."""\n');
  write(dir, 'wallpapers/moon/data/points.json', '[[0, 0], [1, 1]]\n');
  write(dir, 'wallpapers/moon/meta.yaml', MOON_META);
  build(dir, 'rings', 'default', ['16:9'], false, 0);
  build(dir, 'moon', 'default', ['16:9', '10:16'], true, 0);
  build(dir, 'moon', 'late', ['16:9', '10:16'], true, -300);
  build(dir, 'moon', 'open-sea', ['16:9', '10:16'], true, 300);
  write(dir, 'wallpapers/index.json', `${JSON.stringify(INDEX, null, 2)}\n`);
  execFileSync('git', ['init', '-q'], { cwd: dir });
  if (track) execFileSync('git', ['add', 'walldye'], { cwd: dir });
  write(dir, 'wallpapers/.render-lib.sha256', `${renderLibSha(dir)}\n`);
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

const STALE = 'has a stale design_sha (the design, its data or the meta.yaml themes changed)';

describe('check-artifacts', () => {
  it('passes on a current repo, with walldye/ tracked and with it untracked', () => {
    expect(checkArtifacts(repo(true))).toEqual([]);
    expect(checkArtifacts(repo(false))).toEqual([]);
  });

  it('fails every version when design.py or a data file changes', () => {
    const stale = [
      `moon: build/slots.json ${STALE}: run walldye build moon`,
      `moon: build/late/slots.json ${STALE}: run walldye build moon`,
      `moon: build/open-sea/slots.json ${STALE}: run walldye build moon`,
    ];
    const dir = repo();
    appendFileSync(join(dir, 'wallpapers/moon/design.py'), '# edited\n');
    expect(checkArtifacts(dir)).toEqual(stale);
    const data = repo();
    appendFileSync(join(data, 'wallpapers/moon/data/points.json'), '\n');
    expect(checkArtifacts(data)).toEqual(stale);
    const added = repo();
    write(added, 'wallpapers/moon/data/extra.txt', 'x\n');
    expect(checkArtifacts(added)).toEqual(stale);
  });

  it('fails when meta.yaml changes the themes', () => {
    const dir = repo();
    edit(dir, 'wallpapers/rings/meta.yaml', (t) => t.replace('themes: [dark]', 'themes: [dark, light]'));
    expect(checkArtifacts(dir)).toEqual([`rings: build/slots.json ${STALE}: run walldye build rings`]);
  });

  it('fails when a template is edited by hand, in any version', () => {
    const dir = repo();
    edit(dir, 'wallpapers/moon/build/late/10x16.svg', (t) => t.replace('</svg>', '<rect/></svg>'));
    edit(dir, 'wallpapers/rings/build/16x9.svg', (t) => t.replace('</svg>', '<rect/></svg>'));
    expect(checkArtifacts(dir)).toEqual([
      'moon: build/late/10x16.svg does not match its sha256 in slots.json (edited by hand?): run walldye build moon',
      'rings: build/16x9.svg does not match its sha256 in slots.json (edited by hand?): run walldye build rings',
    ]);
  });

  it('fails when a template is missing or unlisted', () => {
    const dir = repo();
    rmSync(join(dir, 'wallpapers/moon/build/open-sea/10x16.svg'));
    writeFileSync(join(dir, 'wallpapers/moon/build/late/21x9.svg'), '<svg/>');
    writeFileSync(join(dir, 'wallpapers/rings/build/21x9.svg'), '<svg/>');
    expect(checkArtifacts(dir)).toEqual([
      'moon: build/late/21x9.svg is not in slots.json: run walldye build moon',
      'moon: build/open-sea/10x16.svg (10:16/dark) is missing: run walldye build moon',
      'rings: build/21x9.svg is not in slots.json: run walldye build rings',
    ]);
  });

  it('fails when a slot count disagrees with the template', () => {
    const dir = repo();
    edit(dir, 'wallpapers/moon/build/late/slots.json', (t) => t.replace('"n":2,', '"n":3,'));
    expect(checkArtifacts(dir)).toContain('moon: build/late/16x9.svg has 2 colour slots, slots.json says 3 for 16:9/dark');
  });

  it("fails when a variant's slots.json names another variant, or the default's names one", () => {
    const dir = repo();
    edit(dir, 'wallpapers/moon/build/late/slots.json', (t) => t.replace('"variant":"late"', '"variant":"open-sea"'));
    edit(dir, 'wallpapers/rings/build/slots.json', (t) => t.replace('"focus"', '"variant":"late","focus"'));
    expect(checkArtifacts(dir)).toEqual([
      'moon: build/late/slots.json has variant "open-sea", not "late": run walldye build moon',
      'rings: build/slots.json has variant "late", but the default\'s has none: run walldye build rings',
    ]);
  });

  it('fails when a listed variant is not built, a build directory is not a variant, or the shapes differ', () => {
    const dir = repo();
    renameSync(join(dir, 'wallpapers/moon/build/open-sea'), join(dir, 'wallpapers/moon/build/old'));
    rmSync(join(dir, 'wallpapers/moon/build/late/10x16.svg'));
    edit(dir, 'wallpapers/moon/build/late/slots.json', (t) => {
      const slots = JSON.parse(t);
      delete slots['10:16/dark'];
      delete slots['10:16/light'];
      return JSON.stringify(slots);
    });
    expect(checkArtifacts(dir)).toEqual([
      'moon: build/late/ has templates for 16:9/dark, 16:9/light, build/ for 10:16/dark, 10:16/light, 16:9/dark, 16:9/light: run walldye build moon',
      'moon: build/open-sea/slots.json is missing: run walldye build moon',
      'moon: build/old/ is not a variant in meta.yaml: run walldye build moon',
    ]);
  });

  it('reports a malformed variants: in meta.yaml', () => {
    const dir = repo();
    edit(dir, 'wallpapers/moon/meta.yaml', (t) => t.replace('default: {label: Full moon}', 'default: {label: Crescent, draft: false}'));
    expect(checkArtifacts(dir)).toEqual([
      'moon: meta.yaml variants.default.draft: the default version is a draft only with the piece',
      'moon: meta.yaml variants.late.label: label repeats the label of default',
    ]);
  });

  it('fails when a slots.json was checked by another walldye version', () => {
    const dir = repo();
    edit(dir, 'wallpapers/moon/build/open-sea/slots.json', (t) => t.replace(`"checked":"${VERSION}"`, '"checked":"0.1.0"'));
    expect(checkArtifacts(dir)).toEqual([`moon: build/open-sea/slots.json was checked by walldye "0.1.0", not ${VERSION}: run walldye build moon`]);
  });

  it('fails when index.json disagrees with meta.yaml, variants included', () => {
    const dir = repo();
    edit(dir, 'wallpapers/rings/meta.yaml', (t) => t.replace('title: Rings', 'title: Circles').replace('draft: false', 'draft: true'));
    edit(dir, 'wallpapers/moon/meta.yaml', (t) => t.replace('New moon, draft: true', 'New moon'));
    expect(checkArtifacts(dir)).toEqual([
      'wallpapers/index.json: moon variants is {"late":{"draft":false,"label":"Crescent"},"open-sea":{"draft":true,"label":"New moon"}}, meta.yaml says {"late":{"draft":false,"label":"Crescent"},"open-sea":{"draft":false,"label":"New moon"}}: run walldye build moon',
      'wallpapers/index.json: rings draft is false, meta.yaml says true: run walldye build rings',
      'wallpapers/index.json: rings title is "Rings", meta.yaml says "Circles": run walldye build rings',
    ]);
  });

  it('fails when index.json lists the wrong pieces or aspects, or is laid out differently', () => {
    const dir = repo();
    const index = JSON.parse(readFileSync(join(dir, 'wallpapers/index.json'), 'utf8'));
    index.moon.aspects = ['16:9'];
    index.ghost = { aspects: ['16:9'], draft: false, license: 'CC0-1.0', title: 'Ghost', variants: {} };
    writeFileSync(join(dir, 'wallpapers/index.json'), `${JSON.stringify(index, null, 2)}\n`);
    expect(checkArtifacts(dir)).toEqual([
      'wallpapers/index.json lists ghost, which has no meta.yaml: run walldye build',
      'wallpapers/index.json: moon aspects is ["16:9"], slots.json says ["16:9","10:16"]: run walldye build moon',
    ]);
    const other = repo();
    edit(other, 'wallpapers/index.json', (t) => `${JSON.stringify(JSON.parse(t))}\n`);
    expect(checkArtifacts(other)).toEqual(['wallpapers/index.json is not laid out the way walldye build writes it: run walldye build']);
    const order = repo();
    edit(order, 'wallpapers/index.json', (t) => t.replace('"draft": false,\n        "label": "Crescent"', '"label": "Crescent",\n        "draft": false'));
    expect(checkArtifacts(order)).toEqual(['wallpapers/index.json is not laid out the way walldye build writes it: run walldye build']);
  });

  it('wants an unbuilt piece reported and left out of index.json', () => {
    const dir = repo();
    rmSync(join(dir, 'wallpapers/rings/build'), { recursive: true });
    expect(checkArtifacts(dir)).toEqual([
      'rings: not built (no build/slots.json): run walldye build rings',
      'wallpapers/index.json lists rings, which is not built: run walldye build rings',
    ]);
    edit(dir, 'wallpapers/index.json', (t) => `${JSON.stringify({ moon: JSON.parse(t).moon }, null, 2)}\n`);
    expect(checkArtifacts(dir)).toEqual(['rings: not built (no build/slots.json): run walldye build rings']);
  });

  it('fails when the render library changes, but not for walldye/tools or untracked files', () => {
    const dir = repo();
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
      ['uv.lock', (t: string) => t.replace('name = "numpy"\nversion = "1.0.0"', 'name = "numpy"\nversion = "1.0.1"')],
      ['.python-version', () => '3.14\n'],
    ] as const) {
      const dir = repo();
      edit(dir, rel, change);
      expect(checkArtifacts(dir), rel).toEqual([
        'the render inputs (walldye/, uv.lock, .python-version) changed since wallpapers/.render-lib.sha256: run walldye build --all',
      ]);
    }
  });

  it('exits 1 from the command line on a stale repo and 0 on a current one', () => {
    const tsx = join(ROOT, 'node_modules/.bin/tsx');
    const script = join(ROOT, 'scripts/check-artifacts.ts');
    const dir = repo();
    const ok = spawnSync(tsx, [script, dir], { encoding: 'utf8' });
    expect(ok.status, ok.stderr).toBe(0);
    expect(ok.stdout).toContain('2 pieces current');
    appendFileSync(join(dir, 'wallpapers/moon/design.py'), '\n');
    const stale = spawnSync(tsx, [script, dir], { encoding: 'utf8' });
    expect(stale.status).toBe(1);
    expect(stale.stderr).toContain(`moon: build/late/slots.json ${STALE}`);
    expect(stale.stderr).toContain('check-artifacts: 3 problems');
  });
});
