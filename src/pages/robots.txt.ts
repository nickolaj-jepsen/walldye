import type { APIRoute } from 'astro';

/** robots.txt: everything may be crawled, and the sitemap is named at the build's `site` (SITE_URL). */
export const GET: APIRoute = ({ site }) =>
  new Response(
    `User-agent: *\nAllow: /\n\nSitemap: ${new URL('/sitemap-index.xml', site).href}\n`,
    {
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    },
  );
