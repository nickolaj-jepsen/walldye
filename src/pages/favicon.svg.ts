import type { APIRoute } from 'astro';
import { faviconSvg } from '../lib/favicon';
import { SYSTEM_PAIR } from '../lib/presets';
import { PRESETS } from '../lib/theme';

/** The icon without JavaScript: SYSTEM_PAIR's dark theme, or its light one under a light system scheme. */
export const GET: APIRoute = () =>
  new Response(faviconSvg(PRESETS[SYSTEM_PAIR[0]], PRESETS[SYSTEM_PAIR[1]]), {
    headers: { 'Content-Type': 'image/svg+xml' },
  });
