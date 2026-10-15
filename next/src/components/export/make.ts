/** Making and saving one export file in the browser. */
import { templateUrl } from '../../lib/catalog';
import type { BakeRows } from '../../lib/template-vars';
import { type ExportJob, rowsOf } from './job';
import { rasterizeSvg, save } from './rasterize';

/** "walldye.com/<slug>" from the canonical URL, so previews and local builds name the real site. */
function pageAddress(): string {
  const href =
    document.querySelector<HTMLLinkElement>('link[rel=canonical]')?.href ?? location.href;
  const url = new URL(href);
  return `${url.host}${url.pathname}`;
}

async function templateText(hash: string): Promise<string> {
  const res = await fetch(templateUrl(hash));
  if (!res.ok) throw new Error(`${templateUrl(hash)}: ${res.status}`);
  return res.text();
}

/**
 * Bakes `job`'s template for its seeds, cuts it to the shape, rasterizes it unless it is an SVG, and
 * saves the file. Rejects when the rows, the template, the bake or the rasterizer fail.
 */
export async function makeExport(
  job: ExportJob,
  rows: Readonly<Record<string, BakeRows>>,
): Promise<void> {
  // The tokenizer behind the bake loads only when a file is made.
  const { aboutLine, rasterFile, regimeTemplate, svgFile } = await import('../../lib/bake');
  const { hash } = regimeTemplate(job.plate, job.seeds);
  const src = { template: await templateText(hash), rows: rowsOf(rows, hash), seeds: job.seeds };
  if (job.format.value === 'svg') {
    const about = aboutLine(pageAddress(), job.variant, job.license, job.token);
    const svg = svgFile(src, job.shape, job.title, about);
    save(new Blob([svg], { type: 'image/svg+xml' }), job.name);
  } else {
    const svg = rasterFile(src, job.shape, job.size[0], job.size[1]);
    save(await rasterizeSvg(svg, job.seeds.bg, job.format.value), job.name);
  }
}
