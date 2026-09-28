/**
 * A second site for the version specs: `astro build` over a generated catalogue (the loader's
 * WALLDYE_WALLPAPERS) whose pieces have named variants, which the real catalogue need not publish.
 * It is built once per Playwright run, whichever worker gets there first, into the run's output
 * directory, and each worker serves it on a port of its own. Not a spec: playwright.config.ts
 * matches `*.spec.ts`.
 */
import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import type { AddressInfo } from 'node:net';
import { dirname, extname, join, resolve, sep } from 'node:path';
import { promisify } from 'node:util';
import { findColours } from '../../src/lib/tokenize';
import { ROOT } from './helpers';

const BG = '#1C1B1A';
const FG = '#DAD8CE';
const ACCENT = '#CF6A4C';
/** Coefficient rows for the three seed colours, which is all these templates use. */
const COEFS: Record<string, number[]> = { [BG]: [1, 0, 0, 0, 0, 0], [FG]: [0, 1, 0, 0, 0, 0], [ACCENT]: [0, 0, 1, 0, 0, 0] };

const CANVAS: Record<string, [number, number]> = { '16:9': [1920, 1080], '10:16': [1080, 1728] };

interface Version {
  focus: [number, number];
  cells: number[];
  /** The template's shapes for a canvas of `w`×`h`, drawn over a BG rectangle. */
  draw: (w: number, h: number) => string;
}

interface FixturePiece {
  meta: string;
  aspects: string[];
  /** Versions by name, `default` first. */
  versions: Record<string, Version>;
}

const horizon = (w: number, h: number) => `<path d="M0 ${Math.round(h * 0.75)}H${w}" stroke="${FG}" stroke-width="2"/>`;

export const PIECES: Record<string, FixturePiece> = {
  'moon-phase': {
    meta: `title: Moon phase
description: A full moon over a flat horizon, drawn as a ring around a disc.
added: 2026-09-28
author: Claude Opus 5.5
ai_generated: true
model: claude-opus-5-5
draft: false
variants:
  default: {label: Full moon}
  crescent:
    label: Crescent
    description: A crescent moon low over a flat horizon, cut from two discs.
  new-moon: {label: New moon, draft: true}
`,
    aspects: ['16:9', '10:16'],
    versions: {
      default: {
        focus: [0.52, 0.44],
        cells: [],
        draw: (w, h) =>
          `${horizon(w, h)}<circle cx="${w * 0.625}" cy="${h * 0.44}" r="200" fill="none" stroke="${FG}" stroke-width="2"/><circle cx="${w * 0.625}" cy="${h * 0.44}" r="160" fill="${ACCENT}"/>`,
      },
      crescent: {
        focus: [0.47, 0.6],
        cells: [6],
        draw: (w, h) => `${horizon(w, h)}<circle cx="${w * 0.36}" cy="${h * 0.6}" r="150" fill="${ACCENT}"/><circle cx="${w * 0.36 + 60}" cy="${h * 0.6 - 30}" r="140" fill="${BG}"/>`,
      },
      'new-moon': {
        focus: [0.5, 0.5],
        cells: [],
        draw: (w, h) => `${horizon(w, h)}<circle cx="${w / 2}" cy="${h / 2}" r="160" fill="none" stroke="${FG}" stroke-width="2"/>`,
      },
    },
  },
  // A published fan work, so the build meets the fan-work rules and the page shows the disclaimer.
  'grid-plain': {
    meta: `title: Plain grid
description: A square grid of hairlines with one cell filled in.
added: 2026-09-27
author: Claude Opus 5.5
ai_generated: true
model: claude-opus-5-5
draft: false
license: LicenseRef-fan-work
franchise: {title: Graph Paper Quest, owner: Example Games}
`,
    aspects: ['16:9'],
    versions: {
      default: {
        focus: [0.5, 0.5],
        cells: [],
        draw: (w, h) =>
          `<path d="${Array.from({ length: 16 }, (_, i) => `M${(i + 1) * 120} 0V${h}`).join('')}" stroke="${FG}"/><rect x="960" y="480" width="120" height="120" fill="${ACCENT}"/>`,
      },
    },
  },
};

/** design.py as the source listing shows it; nothing renders it. */
const DESIGN = `"""A fixture for the site's version tests."""

from walldye import ACCENT, Canvas, P, Params, design, knob


class Moon(Params):
    phase: float = knob(default=0.5, lo=0, hi=1, doc="lit fraction")


@design(aspects=("16:9", "10:16"), variants={"crescent": Moon(phase=0.2)})
def draw(s: Canvas[Moon]) -> None:
    s.fill(P().circle(s.center, 160 * s.params.phase), ACCENT)
`;

const sha256 = (text: string) => createHash('sha256').update(text).digest('hex');

/** A version's template at `aspect`: exactly what a fixture build/ holds. */
export function templateText(slug: string, name: string, aspect: string): string {
  const [w, h] = CANVAS[aspect];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}"><rect width="${w}" height="${h}" fill="${BG}"/>${PIECES[slug].versions[name].draw(w, h)}</svg>\n`;
}

/** The served URL of a version's template, /t/<sha256[:12]>.svg. */
export function templateUrl(slug: string, name: string, aspect: string): string {
  return `/t/${sha256(templateText(slug, name, aspect)).slice(0, 12)}.svg`;
}

function put(path: string, text: string): void {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, text);
}

/** Writes the catalogue into `dir` as `walldye build` lays it out; both regimes share each template. */
function writeCatalogue(dir: string): void {
  for (const [slug, piece] of Object.entries(PIECES)) {
    const folder = join(dir, slug);
    put(join(folder, 'meta.yaml'), piece.meta);
    put(join(folder, 'design.py'), DESIGN);
    for (const [name, v] of Object.entries(piece.versions)) {
      const build = name === 'default' ? join(folder, 'build') : join(folder, 'build', name);
      const slots: Record<string, unknown> = { design_sha: sha256(`${slug} ${name}`) };
      if (name !== 'default') slots.variant = name;
      Object.assign(slots, { focus: v.focus, cells: v.cells, probes: {}, checked: '0.2.0' });
      for (const aspect of piece.aspects) {
        const file = `${aspect.replace(':', 'x')}.svg`;
        const svg = templateText(slug, name, aspect);
        put(join(build, file), svg);
        const colours = findColours(svg).map((c) => c[2]);
        const rows = [...new Set(colours)];
        const entry = { file, sha256: sha256(svg), n: colours.length, coefs: rows.map((c) => COEFS[c]), occ: colours.map((c) => rows.indexOf(c)) };
        slots[`${aspect}/dark`] = entry;
        slots[`${aspect}/light`] = entry;
      }
      put(join(build, 'slots.json'), `${JSON.stringify(slots)}\n`);
    }
  }
}

const run = promisify(execFile);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Builds the fixture site into `home`/dist unless a worker of this run already has, and returns that
 * directory. Astro moves its output in from the project's .astro/, so `home` must be on the same
 * file system as the project.
 */
async function built(home: string): Promise<string> {
  const dist = join(home, 'dist');
  const done = join(home, 'done');
  const lock = join(home, 'lock');
  mkdirSync(home, { recursive: true });
  for (;;) {
    if (existsSync(done)) return dist;
    try {
      mkdirSync(lock);
    } catch {
      await sleep(250);
      continue;
    }
    try {
      if (!existsSync(done)) {
        rmSync(join(home, 'wallpapers'), { recursive: true, force: true });
        writeCatalogue(join(home, 'wallpapers'));
        // Its own cacheDir keeps this build's content store apart from the site's.
        const script = `import { build } from 'astro';
await build({ outDir: ${JSON.stringify(dist)}, cacheDir: ${JSON.stringify(join(home, 'cache'))}, logLevel: 'error' });
process.exit(0);`;
        await run(process.execPath, ['--input-type=module', '-e', script], {
          cwd: ROOT,
          env: { ...process.env, WALLDYE_WALLPAPERS: join(home, 'wallpapers'), ASTRO_TELEMETRY_DISABLED: '1' },
          maxBuffer: 16 * 1024 * 1024,
        });
        writeFileSync(done, '');
      }
    } finally {
      rmSync(lock, { recursive: true, force: true });
    }
  }
}

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.xml': 'application/xml',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.wasm': 'application/wasm',
  '.txt': 'text/plain',
};

/**
 * The fixture site at `url`, served until `close()`; built under `outputDir`, the Playwright run's
 * output directory, which the next run empties. `/x` serves `x.html`, as Pages does for
 * `build.format: 'file'`.
 */
export async function fixtureSite(outputDir: string): Promise<{ url: string; close: () => Promise<void> }> {
  // Workers of one run share the runner as their parent.
  const dist = resolve(await built(join(outputDir, '.versions-site', String(process.ppid))));
  const server = createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname);
    const rel = path === '/' ? 'index.html' : path.slice(1);
    for (const candidate of [rel, `${rel}.html`]) {
      const file = resolve(dist, candidate);
      if (!file.startsWith(dist + sep) || !existsSync(file) || !statSync(file).isFile()) continue;
      res.writeHead(200, { 'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream' });
      res.end(readFileSync(file));
      return;
    }
    res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(existsSync(join(dist, '404.html')) ? readFileSync(join(dist, '404.html')) : 'not found');
  });
  await new Promise<void>((ok) => server.listen(0, '127.0.0.1', ok));
  const { port } = server.address() as AddressInfo;
  return { url: `http://127.0.0.1:${port}`, close: () => new Promise<void>((ok) => server.close(() => ok())) };
}
