/** Sends product events to the site Worker (`src/lib/events.ts` has the model). */
import { type Context, EVENT_PATH, type EventBody } from '../lib/events';
import { presetOf, tokenOf } from '../lib/theme';
import { isPhone, screenPx } from './screen';
import { currentSeeds } from './theme/current';
import { resolveTheme } from './theme/store';

/** `index`, `about` or the slug from the canonical URL; the 404 page is the one without one. */
function pageName(): string {
  const href = document.querySelector<HTMLLinkElement>('link[rel=canonical]')?.href;
  if (!href) return '404';
  const path = new URL(href).pathname.slice(1);
  return path === '' ? 'index' : path;
}

function context(): Context {
  const [w, h] = screenPx();
  const seeds = currentSeeds();
  return {
    page: pageName(),
    w,
    h,
    dpr: devicePixelRatio || 1,
    phone: isPhone(),
    scheme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    theme: presetOf(seeds) ?? 'custom',
    token: tokenOf(seeds),
    source: resolveTheme().source,
  };
}

/** Sends `body` with the page's context, unless the browser sends Global Privacy Control; never throws. */
export function track(body: EventBody): void {
  try {
    if ((navigator as { globalPrivacyControl?: boolean }).globalPrivacyControl === true) return;
    navigator.sendBeacon(EVENT_PATH, JSON.stringify({ ...body, ...context() }));
  } catch {
    // Counting is best effort.
  }
}
