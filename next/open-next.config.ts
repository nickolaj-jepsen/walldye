import { defineCloudflareConfig } from '@opennextjs/cloudflare';
import staticAssetsIncrementalCache from '@opennextjs/cloudflare/overrides/incremental-cache/static-assets-incremental-cache';

// Every route is prerendered and nothing revalidates, so the prerendered pages are served from the
// Worker's static assets: no R2, KV or queue, which keeps it on the free plan.
const config = defineCloudflareConfig({
  incrementalCache: staticAssetsIncrementalCache,
  enableCacheInterception: true,
});

// The package's `build` script runs this CLI, so OpenNext must run `next build` itself.
export default { ...config, buildCommand: 'pnpm exec next build' };
