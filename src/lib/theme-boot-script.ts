/**
 * The theme boot (theme-boot.ts) bundled as an IIFE for Base.astro's inline `<head>` script. With
 * `cache` it is built once per process; without, on every call, so `astro dev` picks up edits.
 * Rejects when the entry is missing or does not compile, which fails the page that asked for it.
 */
import { resolve } from 'node:path';
import { build } from 'esbuild';

// Resolved from the project root: at build time Astro runs this from a bundled chunk, not from src/.
const ENTRY = resolve('src/lib/theme-boot.ts');

let cached: Promise<string> | undefined;

export function themeBootScript(cache = true): Promise<string> {
  const run = () => build({ entryPoints: [ENTRY], bundle: true, format: 'iife', minify: true, write: false }).then((r) => r.outputFiles[0].text);
  if (!cache) return run();
  cached ??= run();
  return cached;
}
