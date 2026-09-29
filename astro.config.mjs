// @ts-check
import { readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { posix } from 'node:path';
import { fileURLToPath } from 'node:url';
import sitemap from '@astrojs/sitemap';
import { defineConfig, fontProviders } from 'astro/config';

const fonts = './src/assets/fonts';

/**
 * Empties `<outDir>/t/` before a build. Astro 7.3's emptyDir skips any top-level entry named ".", "g", "i"
 * or "t" (it passes `new Set(".git")`), so stale templates and slots would otherwise ship with the next build.
 * @returns {import('astro').AstroIntegration}
 */
function cleanTemplates() {
  /** @type {URL | undefined} */
  let outDir;
  return {
    name: 'walldye:clean-templates',
    hooks: {
      'astro:config:done': ({ config }) => {
        outDir = config.outDir;
      },
      'astro:build:start': () => {
        if (outDir) rmSync(new URL('t/', outDir), { recursive: true, force: true });
      },
    },
  };
}

/**
 * Follows each page's module scripts with a `<link rel="modulepreload">` for every chunk they import
 * statically, at any depth, so the browser fetches those chunks alongside the scripts rather than one
 * import level at a time. Reads the imports from the minified chunks, so only `"./x.js"` specifiers count.
 * @returns {import('astro').AstroIntegration}
 */
function preloadImports() {
  return {
    name: 'walldye:preload-imports',
    hooks: {
      'astro:build:done': ({ dir }) => {
        const root = fileURLToPath(dir);
        /** @type {Map<string, string[]>} */
        const direct = new Map();
        /** @param {string} src */
        const importsOf = (src) => {
          let deps = direct.get(src);
          if (!deps) {
            const code = readFileSync(root + src.slice(1), 'utf8');
            deps = [...code.matchAll(/(?:\bfrom|\bimport)\s*"(\.\/[^"]+\.js)"/g)].map((m) =>
              posix.join(posix.dirname(src), m[1]),
            );
            direct.set(src, deps);
          }
          return deps;
        };
        for (const file of readdirSync(root, { recursive: true, encoding: 'utf8' })) {
          if (!file.endsWith('.html')) continue;
          const html = readFileSync(root + file, 'utf8');
          /** @type {Set<string>} */
          const seen = new Set();
          const out = html.replace(
            /<script type="module" src="(\/_astro\/[^"]+\.js)"><\/script>/g,
            (tag, /** @type {string} */ src) => {
              seen.add(src);
              const added = [];
              for (const queue = [src]; queue.length; ) {
                for (const dep of importsOf(/** @type {string} */ (queue.pop()))) {
                  if (seen.has(dep)) continue;
                  seen.add(dep);
                  added.push(dep);
                  queue.push(dep);
                }
              }
              return tag + added.map((dep) => `<link rel="modulepreload" href="${dep}">`).join('');
            },
          );
          if (out !== html) writeFileSync(root + file, out);
        }
      },
    },
  };
}

// https://docs.astro.build/en/reference/configuration-reference/
export default defineConfig({
  site: process.env.SITE_URL || 'https://walldye.com',
  build: { format: 'file' },
  trailingSlash: 'never',
  integrations: [cleanTemplates(), preloadImports(), sitemap()],
  devToolbar: { enabled: false },
  fonts: [
    {
      provider: fontProviders.local(),
      name: 'EB Garamond',
      cssVariable: '--serif',
      fallbacks: ['Garamond', 'Times New Roman', 'serif'],
      display: 'swap',
      options: {
        variants: [
          { src: [`${fonts}/eb-garamond-roman.woff2`], weight: '400 800', style: 'normal' },
          { src: [`${fonts}/eb-garamond-italic.woff2`], weight: '400 800', style: 'italic' },
        ],
      },
    },
    {
      provider: fontProviders.local(),
      name: 'Walldye Mono',
      cssVariable: '--mono',
      fallbacks: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      display: 'swap',
      options: {
        variants: [{ src: [`${fonts}/walldye-mono.woff2`], weight: '400 700', style: 'normal' }],
      },
    },
  ],
  vite: {
    // The export rasterizer runs in a module Worker that imports resvg-wasm.
    worker: { format: 'es' },
  },
});
