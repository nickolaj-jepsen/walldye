// @ts-check
/**
 * Self-hosts the Pyodide runtime the detail page draws with: the pinned npm package's core files and
 * the wheels of PACKAGES and their dependencies, each checked against the sha256 in pyodide-lock.json,
 * under public/py/<version>/, with MANIFEST naming the packages to load and the bytes the worker
 * fetches (for its progress bar). Run by the Astro integration below before every dev server and
 * build, and on its own with `node scripts/pyodide.mjs`; files already present with the right hash
 * are kept.
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** What a design may import besides the standard library: numpy, scipy, shapely and skimage. */
export const PACKAGES = ['numpy', 'scipy', 'shapely', 'scikit-image'];
const CORE = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];
/** Loaded with import() rather than fetched, so the progress bar does not count them. */
const IMPORTED = new Set(['pyodide.mjs', 'pyodide.asm.mjs']);
/** `{packages, bytes}` for src/scripts/draw-worker.ts. */
export const MANIFEST = 'walldye.json';

const require = createRequire(import.meta.url);
const npm = dirname(require.resolve('pyodide/package.json'));
/** The pinned Pyodide version, which names the served directory. */
export const VERSION = /** @type {{ version: string }} */ (JSON.parse(readFileSync(join(npm, 'package.json'), 'utf8'))).version;

const sha256 = (/** @type {Buffer} */ data) => createHash('sha256').update(data).digest('hex');

/**
 * @typedef {{ file_name: string, sha256: string, depends: string[] }} LockEntry
 * @param {Record<string, LockEntry>} lock
 * @returns {LockEntry[]} PACKAGES and everything they depend on, each once.
 */
function closure(lock) {
  const seen = new Map();
  const visit = (/** @type {string} */ dep) => {
    // Lock keys are canonical names; `depends` may spell them with underscores.
    const name = dep.toLowerCase().replace(/[-_.]+/g, '-');
    if (seen.has(name)) return;
    const entry = lock[name];
    if (!entry) throw new Error(`pyodide-lock.json has no package ${name}`);
    seen.set(name, entry);
    entry.depends.forEach(visit);
  };
  PACKAGES.forEach(visit);
  return [...seen.values()];
}

/**
 * Makes `publicDir`/py/<VERSION>/ hold exactly the core files and the wheels, downloading missing
 * or corrupt wheels from the Pyodide CDN, and removes other versions' directories.
 * @param {string} publicDir
 * @param {(message: string) => void} log
 */
export async function ensurePyodide(publicDir, log = console.log) {
  const root = join(publicDir, 'py');
  const dir = join(root, VERSION);
  mkdirSync(dir, { recursive: true });
  for (const old of existsSync(root) ? readdirSync(root) : []) if (old !== VERSION) rmSync(join(root, old), { recursive: true, force: true });
  for (const name of CORE) {
    const data = readFileSync(join(npm, name));
    const target = join(dir, name);
    if (!existsSync(target) || sha256(readFileSync(target)) !== sha256(data)) writeFileSync(target, data);
  }
  const lock = /** @type {{ packages: Record<string, LockEntry> }} */ (JSON.parse(readFileSync(join(npm, 'pyodide-lock.json'), 'utf8')));
  const wheels = closure(lock.packages);
  const keep = new Set([...CORE, MANIFEST, ...wheels.map((w) => w.file_name)]);
  for (const name of readdirSync(dir)) if (!keep.has(name)) rmSync(join(dir, name));
  for (const w of wheels) {
    const target = join(dir, w.file_name);
    if (existsSync(target) && sha256(readFileSync(target)) === w.sha256) continue;
    const url = `https://cdn.jsdelivr.net/pyodide/v${VERSION}/full/${w.file_name}`;
    log(`downloading ${w.file_name}`);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    const data = Buffer.from(await res.arrayBuffer());
    if (sha256(data) !== w.sha256) throw new Error(`${w.file_name}: sha256 differs from pyodide-lock.json`);
    writeFileSync(target, data);
  }
  const fetched = [...CORE.filter((n) => !IMPORTED.has(n)), ...wheels.map((w) => w.file_name)];
  const bytes = fetched.reduce((sum, name) => sum + statSync(join(dir, name)).size, 0);
  const manifest = `${JSON.stringify({ packages: PACKAGES, bytes })}\n`;
  const at = join(dir, MANIFEST);
  if (!existsSync(at) || readFileSync(at, 'utf8') !== manifest) writeFileSync(at, manifest);
}

/**
 * The Astro integration: ensures public/py/<VERSION>/ before the dev server or a build starts.
 * @returns {import('astro').AstroIntegration}
 */
export function pyodide() {
  return {
    name: 'walldye:pyodide',
    hooks: {
      'astro:config:setup': async ({ config, logger }) => {
        await ensurePyodide(fileURLToPath(config.publicDir), (m) => logger.info(m));
      },
    },
  };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await ensurePyodide(resolve('public'));
}
