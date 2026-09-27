// @ts-check
import { rmSync } from 'node:fs';
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

// https://docs.astro.build/en/reference/configuration-reference/
export default defineConfig({
  site: process.env.SITE_URL || 'https://walldye.com',
  build: { format: 'file' },
  trailingSlash: 'never',
  integrations: [cleanTemplates(), sitemap()],
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
    // The export rasteriser runs in a module Worker that imports resvg-wasm.
    worker: { format: 'es' },
  },
});
