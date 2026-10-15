/**
 * The OpenNext target's Worker: OpenNext's own, except that an address that is no page gets the
 * prerendered not-found page with a 404. Static assets are answered before the Worker runs, so a
 * one-segment path outside known-paths.json (a crawler's probe) is a 404 without a render. Any other
 * page OpenNext can only stream after the `[slug]` fallback shell gets the same 404: OpenNext 1.20
 * sends only the streamed part of such a page, without the shell before it.
 */
import openNext from './.open-next/worker.js';
import knownPaths from './src/generated/known-paths.json';

export { BucketCachePurge, DOQueueHandler, DOShardedTagCache } from './.open-next/worker.js';

/** `pnpm build` copies the not-found prerender to 404.html; assets serve it without the extension. */
const NOT_FOUND = '/404';

const KNOWN = new Set<string>(knownPaths);

interface Env {
  ASSETS: { fetch(input: Request | URL | string): Promise<Response> };
}

async function notFound(request: Request, env: Env): Promise<Response> {
  const page = await env.ASSETS.fetch(new URL(NOT_FOUND, request.url));
  return new Response(request.method === 'HEAD' ? null : page.body, {
    status: 404,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'public, max-age=0, must-revalidate',
    },
  });
}

export default {
  async fetch(request: Request, env: Env, ctx: unknown): Promise<Response> {
    const read = request.method === 'GET' || request.method === 'HEAD';
    const segment = /^\/([^/]+)$/.exec(new URL(request.url).pathname)?.[1];
    if (read && segment !== undefined && !KNOWN.has(segment)) {
      return notFound(request, env);
    }
    const response = await openNext.fetch(request, env, ctx);
    // Every real page is prerendered whole, so only an unknown param reaches a postponed render.
    if (read && !request.headers.has('rsc') && response.headers.get('x-nextjs-postponed') === '1') {
      await response.body?.cancel();
      return notFound(request, env);
    }
    return response;
  },
};
