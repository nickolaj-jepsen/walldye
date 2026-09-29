import { readFile } from 'node:fs/promises';
import { type Download, expect, type Page, test } from '@playwright/test';

/** Width, height and color type from a PNG's IHDR chunk. */
function pngHeader(buf: Buffer): { width: number; height: number; colorType: number } {
  expect(buf.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20), colorType: buf[25] };
}

async function download(page: Page): Promise<{ dl: Download; buf: Buffer }> {
  const [dl] = await Promise.all([
    page.waitForEvent('download', { timeout: 90_000 }),
    page.click('#download'),
  ]);
  const path = await dl.path();
  return { dl, buf: await readFile(path!) };
}

const pick = (page: Page, name: string, value: string) =>
  page.locator(`#export input[name=${name}][value="${value}"]`).check({ force: true });

/** Moves the crop range the way a keyboard or pointer would: set the value, fire `input`. */
const setCrop = (page: Page, value: number) =>
  page.locator('#crop').evaluate((el, v) => {
    (el as HTMLInputElement).value = String(v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }, value);

test.describe('detail', () => {
  test.use({
    colorScheme: 'dark',
    viewport: { width: 1440, height: 1000 },
    // A 16:9 screen at 2560×1440, so the page starts on 16:9 and "your screen" is the default size's pixels.
    deviceScaleFactor: 1,
    contextOptions: { screen: { width: 2560, height: 1440 } },
  });

  test('a shape without its own template shows a crop window that follows the range and a drag', async ({
    page,
  }) => {
    await page.goto('/schotter');
    await expect(page.locator('.spread .plate > img')).toHaveAttribute('src', /^\/t\//);
    await expect(page.locator('.spread .crop')).toBeHidden();
    await expect(page.locator('#crop-row')).toBeHidden();
    // A Download under the attribution, on the first screen, starts on your screen.
    await expect(page.locator('#quick-download')).toBeInViewport();
    await expect(page.locator('#quick-download')).toHaveText(
      'Download PNG, 2560×1440 for your screen',
    );
    await expect(page.locator('#export input[name=size][value=screen]')).toBeChecked();

    await pick(page, 'asp', '16:10');
    await expect(page.locator('.spread .crop')).toBeVisible();
    await expect(page.locator('#shape-hint')).toBeVisible();
    await expect(page.locator('#crop-row')).toBeVisible();
    // Centered on the piece's focus from slots.json (x 0.4633 → 0.133 of the travel).
    await expect(page.locator('#crop')).toHaveValue('0.133');
    // An unplaced crop follows the focus, so the address carries no position.
    expect(new URL(page.url()).search).toBe('?shape=16x10');
    await expect(page.locator('#download')).toHaveAttribute(
      'title',
      'schotter-fireproof-2560x1600.png',
    );
    await expect(page.locator('#sizes input:enabled')).toHaveCount(5);
    await expect(page.locator('#sizes label:visible')).toHaveCount(5);
    await expect(page.locator('#run-render')).toHaveText(
      'uv run walldye render schotter --theme fireproof --crop 25.536,0,1728,1080 -o schotter-fireproof-16x10-crop.svg',
    );

    await setCrop(page, 1);
    expect(new URL(page.url()).searchParams.get('crop')).toBe('1');
    await expect(page.locator('#run-render')).toContainText('--crop 192,0,1728,1080');

    await page.evaluate(() => scrollTo(0, 0));
    const win = await page.locator('.spread .crop').boundingBox();
    await page.mouse.move(win!.x + win!.width / 2, win!.y + win!.height / 2);
    await page.mouse.down();
    await page.mouse.move(win!.x + win!.width / 2 - 2000, win!.y + win!.height / 2, { steps: 4 });
    await page.mouse.up();
    await expect(page.locator('#crop')).toHaveValue('0');

    // The crop survives a reload through the query string.
    await page.reload();
    await expect(page.locator('#export input[name=asp][value="16:10"]')).toBeChecked();
    await expect(page.locator('#crop')).toHaveValue('0');
  });

  test('PNG export is RGB at the exact size', async ({ page }) => {
    await page.goto('/schotter?shape=21x9&crop=0.5');
    await pick(page, 'size', '3440x1440');
    await expect(page.locator('#download')).toHaveAttribute(
      'title',
      'schotter-fireproof-3440x1440.png',
    );
    const { dl, buf } = await download(page);
    expect(dl.suggestedFilename()).toBe('schotter-fireproof-3440x1440.png');
    expect(pngHeader(buf)).toEqual({ width: 3440, height: 1440, colorType: 2 });
  });

  test('JPEG export has the right size', async ({ page }) => {
    await page.goto('/radar-sweep');
    await pick(page, 'fmt', 'jpeg');
    await pick(page, 'size', '1920x1080');
    const { dl, buf } = await download(page);
    expect(dl.suggestedFilename()).toBe('radar-sweep-fireproof-1920x1080.jpg');
    expect(buf.subarray(0, 3).toString('hex')).toBe('ffd8ff');
  });

  test('SVG export is recolored, cut to the crop and titled', async ({ page }) => {
    await page.goto('/schotter?t=nord');
    await pick(page, 'fmt', 'svg');
    await pick(page, 'asp', '9:19.5');
    await setCrop(page, 0);
    await expect(page.locator('#download')).toHaveAttribute(
      'title',
      'schotter-nord-9x19.5-crop.svg',
    );
    const { dl, buf } = await download(page);
    expect(dl.suggestedFilename()).toBe('schotter-nord-9x19.5-crop.svg');
    const svg = buf.toString('utf8');
    expect(svg).toMatch(/^<svg [^>]*viewBox="0 0 498\.4615 1080" width="498\.4615" height="1080"/);
    expect(svg).toContain(
      '<title>Squares shaking loose</title><desc>walldye.com/schotter · CC0-1.0 · theme nord</desc>',
    );
    expect(svg).toContain('#2E3440');
    expect(svg).not.toContain('#1C1B1A');
  });

  test('a native shape exports its own template with crisp cells', async ({ page }) => {
    await page.goto('/dither-moon');
    await pick(page, 'asp', '9:19.5');
    await expect(page.locator('.spread .crop')).toBeHidden();
    await expect(page.locator('#shape-hint')).toBeHidden();
    // The old image stays until the new one has faded in over it.
    await expect(page.locator('.spread .plate > img')).toHaveCount(1);
    await expect(page.locator('.spread .plate > img')).toHaveAttribute('data-aspect', '9:19.5');
    // The shape's frame must not take the plate's height with it.
    const plate = await page.locator('.spread .plate').boundingBox();
    expect(plate!.height / plate!.width).toBeCloseTo(9 / 16, 2);
    await expect(page.locator('#run-render')).toHaveText(
      'uv run walldye render dither-moon --theme fireproof --aspect 9:19.5 -o dither-moon-fireproof-9x19.5.svg',
    );
    // 1170 px over a 1080-unit canvas puts 3-unit cells at 3.25 px.
    await pick(page, 'size', '1170x2532');
    await expect(page.locator('#cell-note')).toHaveText(
      'At this size the squares come out 3 or 4 pixels wide.',
    );
    await pick(page, 'size', '1080x2340');
    await expect(page.locator('#cell-note')).toBeHidden();

    await pick(page, 'fmt', 'svg');
    const { buf } = await download(page);
    const svg = buf.toString('utf8');
    expect(svg).toMatch(/^<svg [^>]*viewBox="0 0 1080 2340"/);
    expect(svg).toMatch(/<path shape-rendering="crispEdges" [^>]*class="px"/);
  });

  test('there are no neighbor links and the arrow keys do nothing', async ({ page }) => {
    await page.goto('/radar-sweep');
    await expect(page.locator('.label')).toBeVisible();
    await expect(page.locator('nav.crumbs, a[rel=prev], a[rel=next]')).toHaveCount(0);
    await expect(page.locator('main a', { hasText: /^(← Index|Previous:|Next:)/ })).toHaveCount(0);
    // The label ends with the facts list.
    expect(
      await page.locator('.label > :last-child').evaluate((el) => el.matches('dl.facts')),
    ).toBe(true);

    await page.evaluate(() => {
      (window as unknown as { prevented: string[] }).prevented = [];
      addEventListener('keydown', (e) => {
        if (e.defaultPrevented)
          (window as unknown as { prevented: string[] }).prevented.push(e.key);
      });
    });
    for (const key of ['ArrowLeft', 'ArrowRight']) await page.locator('body').press(key);
    await page.waitForTimeout(150);
    expect(new URL(page.url()).pathname).toBe('/radar-sweep');
    expect(
      await page.evaluate(() => (window as unknown as { prevented: string[] }).prevented),
    ).toEqual([]);
  });

  test('f is ignored with modifiers, in fields, listings and editable text, and while the picker is open', async ({
    page,
  }) => {
    // schotter crops every other shape, so the crop range is there to focus.
    await page.goto('/schotter');
    const fullscreen = () => page.evaluate(() => document.fullscreenElement !== null);
    /** Presses `key` on whatever `focus` focuses, then checks fullscreen did not start. */
    const ignored = async (key: string, focus: () => Promise<void>) => {
      await focus();
      await page.keyboard.press(key);
      await page.waitForTimeout(100);
      expect(await fullscreen(), `${key} leaked`).toBe(false);
    };
    const body = () => page.locator('body').focus();

    for (const key of ['Shift+F', 'Control+f', 'Alt+f', 'Meta+f']) await ignored(key, body);

    await page.locator('#export').scrollIntoViewIfNeeded();
    await ignored('f', () => page.locator('#export input[name=fmt][value=svg]').focus());
    await pick(page, 'asp', '16:10');
    await expect(page.locator('#crop')).toBeVisible();
    await ignored('f', () => page.locator('#crop').focus());
    await page.locator('.appendix > summary').click();
    await ignored('f', () => page.locator('.listing pre').focus());
    await ignored('f', () => page.locator('.run pre').focus());
    await page.evaluate(() => {
      const box = document.createElement('div');
      box.id = 'editable';
      box.contentEditable = 'true';
      box.textContent = 'x';
      const area = document.createElement('textarea');
      area.id = 'area';
      document.querySelector('.label-more')!.append(box, area);
    });
    await ignored('f', () => page.locator('#editable').focus());
    await ignored('f', () => page.locator('#area').focus());

    await page.click('#theme-button');
    await ignored('f', () => page.locator('#picker button[data-preset=nord]').focus());
    await ignored('f', () => page.locator('#seed-bg').focus());
    await page.keyboard.press('Escape');
    await expect(page.locator('#picker')).toBeHidden();
  });

  test('f toggles fullscreen on the plate', async ({ page, browserName }) => {
    test.skip(browserName === 'webkit', 'headless WebKit has no fullscreen');
    await page.goto('/schotter');
    await page.locator('body').press('f');
    await expect
      .poll(() =>
        page.evaluate(() => document.fullscreenElement?.classList.contains('plate') ?? false),
      )
      .toBe(true);
    await page.locator('body').press('f');
    await expect.poll(() => page.evaluate(() => document.fullscreenElement === null)).toBe(true);
  });

  test('WebP exports where the browser can encode it, and is refused with a reason elsewhere', async ({
    page,
  }) => {
    await page.goto('/radar-sweep');
    const webp = page.locator('#export input[name=fmt][value=webp]');
    await page.locator('#export').scrollIntoViewIfNeeded();
    const supported = await page.evaluate(async () => {
      const c = new OffscreenCanvas(1, 1);
      c.getContext('2d');
      return (await c.convertToBlob({ type: 'image/webp' })).type === 'image/webp';
    });
    if (!supported) {
      await expect(webp).toBeDisabled();
      await expect(page.locator('#format-hint')).toBeVisible();
      return;
    }
    await expect(page.locator('#format-hint')).toBeHidden();
    await webp.check({ force: true });
    await pick(page, 'size', '1920x1080');
    const { dl, buf } = await download(page);
    expect(dl.suggestedFilename()).toBe('radar-sweep-fireproof-1920x1080.webp');
    expect(buf.subarray(0, 4).toString()).toBe('RIFF');
    expect(buf.subarray(8, 12).toString()).toBe('WEBP');
  });

  test('Copy takes the raw design.py', async ({ page, context, browserName }) => {
    test.skip(browserName !== 'chromium', 'clipboard permissions are Chromium-only in Playwright');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.goto('/schotter');
    await page.locator('.appendix > summary').click();
    await page.click('[data-action=copy-source]');
    await expect(page.locator('[data-action=copy-source]')).toHaveText('Copied');
    const text = await page.evaluate(() => navigator.clipboard.readText());
    expect(text.startsWith('"""A band of square outlines')).toBe(true);
    expect(text).toContain('def draw(');
  });
});

test.describe('detail on a phone', () => {
  test.skip(({ browserName }) => browserName === 'firefox', 'Firefox has no mobile emulation');
  test.use({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    hasTouch: true,
    isMobile: true,
    colorScheme: 'light',
  });

  test('starts on your screen, in the nearest shape', async ({ page }) => {
    await page.goto('/schotter');
    await expect(page.locator('#export input[name=asp][value="9:19.5"]')).toBeChecked();
    await expect(page.locator('#export input[name=size][value=screen]')).toBeChecked();
    await expect(page.locator('#download')).toHaveAttribute(
      'title',
      'schotter-flexoki-light-1170x2532.png',
    );
    // The phone default is not written to the address.
    expect(new URL(page.url()).search).toBe('');
  });

  test('the plate takes its tall shape before the page module loads', async ({ page }) => {
    // Without the module only the inline shape boot runs, so the plate size cannot change later.
    await page.route('**/_astro/*.js', (route) => route.abort());
    await page.goto('/schotter');
    await expect(page.locator('.spread')).toHaveAttribute('data-aspect', '9:19.5');
    const box = await page.locator('.spread .plate').boundingBox();
    expect(box!.height / box!.width).toBeGreaterThan(2);
  });

  test('a tall shape shows the crop in the plate, moved by a drag, with the window on a map', async ({
    page,
  }) => {
    await page.goto('/schotter');
    const plate = page.locator('.spread .plate');
    await expect(plate.locator('> img')).toHaveAttribute('data-aspect', '16:9');
    const box = await plate.boundingBox();
    expect(box!.height / box!.width).toBeGreaterThan(2);
    await expect(plate.locator('> .crop')).toBeHidden();
    await expect(page.locator('.crop-map .crop')).toBeVisible();
    // The plate, title, attribution and Download share the first screen.
    await expect(page.locator('#quick-download')).toBeInViewport();

    // Dragging the picture left shows more of its right side.
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await page.mouse.down();
    await page.mouse.move(box!.x + box!.width / 2 - 2000, box!.y + box!.height / 2, { steps: 4 });
    await page.mouse.up();
    await expect(page.locator('#crop')).toHaveValue('1');
    await expect(plate).toHaveCSS('--pos', '100% 0%');
    expect(new URL(page.url()).searchParams.get('crop')).toBe('1');

    // A shape wider than the screen keeps 16:9 with the crop window.
    await pick(page, 'asp', '16:10');
    await expect(plate.locator('> .crop')).toBeVisible();
    await expect(page.locator('.crop-map')).toBeHidden();
  });

  test('the Download under the attribution follows the export panel and saves its file', async ({
    page,
  }) => {
    await page.goto('/schotter');
    const quick = page.locator('#quick-download');
    // Narrow phones leave out "for your screen", keeping the line to one.
    await expect(quick).toHaveText('Download PNG, 1170×2532', { useInnerText: true });
    await pick(page, 'fmt', 'svg');
    await expect(quick).toHaveText('Download SVG, 9:19.5', { useInnerText: true });
    await pick(page, 'fmt', 'jpeg');
    const [dl] = await Promise.all([
      page.waitForEvent('download', { timeout: 90_000 }),
      quick.click(),
    ]);
    expect(dl.suggestedFilename()).toBe(await quick.getAttribute('title'));
  });
});

test.describe('detail on a very large screen', () => {
  test.skip(({ browserName }) => browserName === 'firefox', 'Firefox ignores screen emulation');
  // `screen` is not a test option of its own; it goes through contextOptions.
  test.use({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
    contextOptions: { screen: { width: 7680, height: 4320 } },
  });

  test('refuses your screen with a reason', async ({ page }) => {
    await page.goto('/radar-sweep');
    await expect(page.locator('#export input[name=size][value=screen]')).toBeDisabled();
    await expect(page.locator('#export input[name=size][value=screen]')).toHaveAttribute(
      'aria-describedby',
      'size-limit',
    );
    await expect(page.locator('#size-limit')).toBeVisible();
    await expect(page.locator('#export input[name=size][value="2560x1440"]')).toBeChecked();
  });
});
