/**
 * A client entry bundled as an IIFE for an inline `<script>`: the theme and transition boots in
 * Base.astro's `<head>` and the index's and detail page's shape boots. With `cache` each entry is built once per process; without, on every
 * call, so `astro dev` picks up edits. Rejects when the entry is missing or does not compile, which
 * fails the page that asked for it.
 */
import { resolve } from 'node:path';
import { build } from 'esbuild';

/** Entries by name, resolved from the project root: at build time Astro runs this from a bundled chunk, not from src/. */
const ENTRIES = {
  theme: resolve('src/client/theme/boot.ts'),
  transition: resolve('src/client/transition/boot.ts'),
  shape: resolve('src/client/index/shape-boot.ts'),
  detailShape: resolve('src/client/detail/shape-boot.ts'),
} as const;

const cached = new Map<keyof typeof ENTRIES, Promise<string>>();

export function inlineScript(entry: keyof typeof ENTRIES, cache = true): Promise<string> {
  const run = () =>
    build({
      entryPoints: [ENTRIES[entry]],
      bundle: true,
      format: 'iife',
      minify: true,
      write: false,
    }).then((r) => r.outputFiles[0].text);
  if (!cache) return run();
  let p = cached.get(entry);
  if (!p) {
    p = run();
    cached.set(entry, p);
  }
  return p;
}
