/**
 * The detail page's export: making the file the Download buttons ask for and saving it, their busy
 * state, and falling back from WebP where the browser cannot encode it.
 */
import { type Aspect, DEFAULT_VARIANT, type FORMATS } from '../../lib/content';
import { crispPixels, type ExportShape, rasterSvg, svgExport } from '../../lib/shape';
import type { Seeds } from '../../lib/theme';
import { must } from '../dom';
import { track } from '../events';
import {
  canEncodeWebp,
  prefetchRasterizer,
  type RasterFormat,
  rasterizeSvg,
  save,
} from '../export/rasterize';
import { getSlots, type PlateData, recolored } from '../plates';

/** Everything one Download needs, read from the page when it is pressed. */
export interface ExportJob {
  variant: string;
  data: PlateData;
  /** The template aspect to read: the shape's own, else 16:9 to crop. */
  source: Aspect;
  shape: ExportShape;
  seeds: Seeds;
  token: string;
  format: (typeof FORMATS)[number];
  size: [number, number];
  /** Whether the visitor chose the screen's own size. */
  screen: boolean;
  name: string;
}

export interface ExportPage {
  panel: HTMLElement;
  buttons: HTMLButtonElement[];
  error: HTMLElement;
  formatRadios: HTMLInputElement[];
  formatHint: HTMLElement;
  slug: string;
  /** The job for the current state. */
  job: () => ExportJob;
  /** Called after the WebP fallback changed the chosen format. */
  onFormatChange: () => void;
}

/** Wires the Download buttons of `page` and, once the panel or a button is seen, the rasterizer and the WebP check. */
export function setUpExport(page: ExportPage): void {
  const { panel, buttons, error, formatRadios, formatHint } = page;
  const title = document.querySelector('.label h1')?.textContent?.trim() ?? page.slug;
  const license = panel.dataset.license ?? '';
  // "walldye.com/<slug>" from the canonical URL, so previews and local builds name the real site.
  const href =
    document.querySelector<HTMLLinkElement>('link[rel=canonical]')?.href ?? location.href;
  const address = `${new URL(href).host}${new URL(href).pathname}`;
  let busy = false;
  let first = true;

  const preparing = (on: boolean) => {
    for (const btn of buttons) {
      if (on) btn.setAttribute('aria-busy', 'true');
      else btn.removeAttribute('aria-busy');
      must('.k', btn).textContent = on ? 'Preparing…' : 'Download';
    }
  };

  /** Makes and saves the file; a failure writes the error and, from `from` outside the panel, scrolls it into view. */
  const run = async (from: HTMLElement) => {
    if (busy) return;
    busy = true;
    preparing(true);
    error.textContent = '';
    try {
      const j = page.job();
      const slots = await getSlots(j.data.slots);
      const r = await recolored(j.data, j.source, j.seeds);
      const svg = Array.isArray(slots.cells) && slots.cells.length ? crispPixels(r.svg) : r.svg;
      let size = 'svg';
      if (j.format.value === 'svg') {
        const at = j.variant === DEFAULT_VARIANT ? address : `${address}?v=${j.variant}`;
        const about = [at, license, `theme ${j.token}`].filter(Boolean).join(' · ');
        save(new Blob([svgExport(svg, j.shape, title, about)], { type: 'image/svg+xml' }), j.name);
      } else {
        const raster = rasterSvg(svg, j.shape, ...j.size);
        save(await rasterizeSvg(raster.svg, j.seeds.bg, j.format.value as RasterFormat), j.name);
        size = j.screen ? 'screen' : `${j.size[0]}x${j.size[1]}`;
      }
      track({
        event: 'export',
        slug: page.slug,
        version: j.variant,
        format: j.format.value,
        aspect: j.shape.aspect,
        size,
        first,
      });
      first = false;
    } catch {
      error.textContent = 'The file could not be made.';
      if (!panel.contains(from)) error.scrollIntoView({ block: 'center' });
    } finally {
      busy = false;
      preparing(false);
    }
  };

  for (const btn of buttons) btn.addEventListener('click', () => void run(btn));

  const seen = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    seen.disconnect();
    prefetchRasterizer();
    canEncodeWebp().then((ok) => {
      const webp = formatRadios.find((r) => r.value === 'webp');
      if (!webp || ok) return;
      webp.disabled = true;
      webp.setAttribute('aria-describedby', 'format-hint');
      formatHint.hidden = false;
      if (webp.checked) {
        for (const r of formatRadios) r.checked = r.value === 'png';
        page.onFormatChange();
      }
    });
  });
  seen.observe(panel);
  for (const btn of buttons) if (!panel.contains(btn)) seen.observe(btn);
}
