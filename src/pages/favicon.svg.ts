import type { APIRoute } from 'astro';
import { faviconSvg } from '../lib/favicon';
import { PRESETS } from '../lib/theme';

/** The icon without JavaScript: fireproof, or flexoki-light when the system prefers a light scheme. */
export const GET: APIRoute = () =>
  new Response(faviconSvg(PRESETS.fireproof, PRESETS['flexoki-light']), {
    headers: { 'Content-Type': 'image/svg+xml' },
  });
