import type { NextConfig } from 'next';

// `NEXT_OUTPUT=export` writes a static site to out/ (Workers static assets, no script); the default
// build is the one @opennextjs/cloudflare wraps. Both prerender every route. Next 16.4 refuses
// `output: 'export'` with Cache Components (its PPR), so the export keeps `use cache` through
// `experimental.useCache` alone.
const staticExport = process.env.NEXT_OUTPUT === 'export';

const nextConfig: NextConfig = {
  ...(staticExport
    ? { output: 'export' as const, experimental: { useCache: true } }
    : { cacheComponents: true, partialPrefetching: true }),
  // The repo root has its own lockfile; this app resolves everything from its own folder.
  turbopack: { root: process.cwd() },
  outputFileTracingRoot: process.cwd(),
  // Grid links prefetch a page's own content on intent with `prefetch`, which the export has no server to answer.
  env: { WALLDYE_LINK_PREFETCH: staticExport ? '' : '1' },
  reactCompiler: true,
  typedRoutes: true,
  trailingSlash: false,
  poweredByHeader: false,
  images: { unoptimized: true },
  cacheLife: {
    // The catalog changes only with a deploy, which starts a new cache; nothing revalidates by time.
    catalog: { stale: Infinity, revalidate: Infinity, expire: Infinity },
  },
};

export default nextConfig;
