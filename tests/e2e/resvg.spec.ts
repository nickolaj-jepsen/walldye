import { readdirSync, readFileSync } from 'node:fs';
import type { Page } from '@playwright/test';
import { rasterSvg } from '../../src/lib/shape';
import { decodeRgb, MANIFEST, type PixelDiff, pixelDiff, ROOT } from './helpers';
import { expect, test } from './test';

const REF = MANIFEST.resvg;
const reference = () => decodeRgb(readFileSync(`${ROOT}${REF.png}`));

/** The built asset in dist/_astro whose name matches `pattern`, as a site path. */
function builtAsset(pattern: RegExp): string {
  const name = readdirSync(`${ROOT}dist/_astro`).find((f) => pattern.test(f));
  expect(name, `no ${pattern} in dist/_astro; run astro build`).toBeTruthy();
  return `/_astro/${name}`;
}

function report(what: string, diff: PixelDiff): void {
  test.info().annotations.push({
    type: 'resvg',
    description: `${what} against resvg-py ${REF.resvg_py}: max ${diff.max}, mean ${diff.mean.toFixed(4)}, >1 in ${diff.overOne} channels`,
  });
}

/** Downloads the PNG the export panel makes at `width`×`height`, a size the panel does not offer. */
async function exportAt(page: Page, width: number, height: number): Promise<Buffer> {
  await page.locator('#sizes').evaluate((sizes, value) => {
    const label = document.createElement('label');
    // Offered for the chosen shape, like the panel's own sizes.
    label.dataset.aspect = document.querySelector<HTMLInputElement>(
      '#export input[name=asp]:checked',
    )?.value;
    label.innerHTML = `<input type="radio" name="size" value="${value}"><span>${value}</span>`;
    sizes.append(label);
  }, `${width}x${height}`);
  await page.locator(`#sizes input[value="${width}x${height}"]`).check({ force: true });
  await expect(page.locator('#download')).toHaveAttribute(
    'title',
    `schotter-nord-${width}x${height}.png`,
  );
  const [dl] = await Promise.all([
    page.waitForEvent('download', { timeout: 90_000 }),
    page.click('#download'),
  ]);
  return readFileSync((await dl.path())!);
}

test.describe('resvg-wasm', () => {
  test('the bundled export worker draws the reference SVG like resvg-py', async ({ page }) => {
    await page.goto('/schotter');
    const svg = rasterSvg(
      readFileSync(`${ROOT}${REF.svg}`, 'utf8'),
      { aspect: '16:9', native: true, t: 0 },
      REF.width,
      REF.height,
    ).svg;
    const png = await page.evaluate(
      async ({ workerUrl, wasmUrl, svg, background }) => {
        const wasm = await WebAssembly.compile(await (await fetch(wasmUrl)).arrayBuffer());
        const worker = new Worker(workerUrl, { type: 'module' });
        try {
          const res = await new Promise<{ ok: boolean; blob?: Blob; error?: string }>(
            (resolve, reject) => {
              worker.onmessage = (e) => resolve(e.data);
              worker.onerror = (e) => reject(new Error(e.message));
              worker.postMessage({ wasm, svg, background, format: 'png', quality: 0.92 });
            },
          );
          if (!res.ok || !res.blob) throw new Error(res.error ?? 'no PNG');
          return [...new Uint8Array(await res.blob.arrayBuffer())];
        } finally {
          worker.terminate();
        }
      },
      {
        workerUrl: builtAsset(/^worker-.*\.js$/),
        wasmUrl: builtAsset(/^index_bg\..*\.wasm$/),
        svg,
        background: REF.background,
      },
    );
    const got = decodeRgb(Uint8Array.from(png));
    const diff = pixelDiff(got, reference());
    report('worker', diff);
    expect(diff.max, JSON.stringify(diff)).toBeLessThanOrEqual(2);
    expect(diff.overOne).toBe(0);
  });

  test('a PNG exported under nord matches the resvg-py render of the Python output', async ({
    page,
  }) => {
    await page.goto('/schotter?t=nord');
    await page.locator('#export').scrollIntoViewIfNeeded();
    const got = decodeRgb(await exportAt(page, REF.width, REF.height));
    // The browser recolor is within 2 units of the Python render slot by slot, so the pixels are too.
    const diff = pixelDiff(got, reference());
    report('export panel', diff);
    expect(diff.max, JSON.stringify(diff)).toBeLessThanOrEqual(3);
  });
});
