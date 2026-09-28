/**
 * The inline script in the index's `<head>` (index.astro bundles it), after the theme boot: on an
 * address with no query, starts the downloads the first plates' recolor begins with, so they need
 * not wait for the page module and its chunks. Mirrors sourceFor() and recolored() in plates.ts;
 * a request they do not make goes unused. On any failure the page module loads everything itself.
 */
import { CANVAS } from '../../lib/content';
import { isFireproof, parseToken, regimeOf } from '../../lib/theme';
import { deviceAspect } from '../screen';

/** One of the first plates as index.astro lists it in `data-first`: every template key's URL, and its slots.json. */
interface First {
  templates: Record<string, string>;
  slots: string;
}

try {
  const seeds = parseToken(document.documentElement.dataset.theme);
  const data = document.currentScript?.dataset.first;
  if (!location.search && seeds && data) {
    const shape = deviceAspect();
    const regime = regimeOf(seeds);
    const [w, h] = CANVAS[shape];
    // As many as the first row holds: one column below the filter's breakpoint, tall shapes two.
    const count = matchMedia('(min-width: 60.0625rem)').matches ? 4 : w < h ? 2 : 1;
    // Fetched rather than preloaded, since WebKit never hands a fetch preload to fetch().
    const early = new Map<string, Promise<Response>>();
    const start = (url: string | undefined) => {
      if (!url) return;
      const res = fetch(url);
      res.catch(() => {});
      early.set(url, res);
    };
    for (const p of (JSON.parse(data) as First[]).slice(0, count)) {
      const source = `${shape}/${regime}` in p.templates ? shape : '16:9';
      if (isFireproof(seeds) && source === '16:9') {
        const link = Object.assign(document.createElement('link'), {
          rel: 'preload',
          as: 'image',
          href: p.templates['16:9/dark'],
          fetchPriority: 'high',
        });
        document.head.append(link);
      } else {
        start(p.slots);
        start(p.templates[`${source}/${regime}`]);
      }
    }
    window.walldyePlateFetches = early;
  }
} catch {
  // plates.ts fetches what this did not start.
}
