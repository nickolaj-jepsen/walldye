import type { Page } from '@playwright/test';
import { expect, test } from './test';

/** Every event the page posts to /e, answered 204 as the Worker would; `astro preview` has no /e. */
async function recordEvents(page: Page): Promise<Record<string, unknown>[]> {
  const events: Record<string, unknown>[] = [];
  await page.route('**/e', async (route) => {
    const req = route.request();
    if (req.method() === 'POST') events.push(JSON.parse(req.postData() ?? 'null'));
    await route.fulfill({ status: 204 });
  });
  return events;
}

const ofKind = (events: Record<string, unknown>[], name: string) =>
  events.filter((e) => e.event === name);

test.describe('events', () => {
  test.use({
    colorScheme: 'dark',
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
    contextOptions: { screen: { width: 2560, height: 1440 } },
  });

  test('an export is counted once the file is saved, first only the first time', async ({
    page,
  }) => {
    const events = await recordEvents(page);
    await page.goto('/loose-squares');
    for (const fmt of ['png', 'svg']) {
      await page.locator(`#export input[name=fmt][value=${fmt}]`).check({ force: true });
      await Promise.all([
        page.waitForEvent('download', { timeout: 90_000 }),
        page.click('#download'),
      ]);
    }
    await expect.poll(() => ofKind(events, 'export').length).toBe(2);
    const context = {
      page: 'loose-squares',
      w: 2560,
      h: 1440,
      dpr: 1,
      phone: false,
      scheme: 'dark',
      theme: 'fireproof',
      token: 'fireproof',
      source: 'system',
    };
    const common = { event: 'export', slug: 'loose-squares', version: 'default', aspect: '16:9' };
    expect(ofKind(events, 'export')).toEqual([
      { ...common, format: 'png', size: 'screen', first: true, ...context },
      { ...common, format: 'svg', size: 'svg', first: false, ...context },
    ]);
    expect(events).toHaveLength(2);
  });

  test('a preset click is one theme event', async ({ page }) => {
    const events = await recordEvents(page);
    await page.goto('/');
    await page.locator('.themes button[data-preset=nord]').click();
    await expect.poll(() => events.length).toBe(1);
    expect(events[0]).toMatchObject({
      event: 'theme',
      kind: 'preset',
      name: 'nord',
      via: 'index',
      page: 'index',
      theme: 'nord',
      token: 'nord',
      source: 'saved',
    });
  });

  test('custom edits in the picker are one theme event when it closes', async ({ page }) => {
    const events = await recordEvents(page);
    await page.goto('/about');
    await page.click('#theme-button');
    await page.fill('#seed-bg', '#112233');
    await page.fill('#seed-accent', '#FF8800');
    await expect(page.locator('html')).toHaveAttribute('data-theme', /^112233-/);
    expect(events).toHaveLength(0);
    await page.keyboard.press('Escape');
    await expect.poll(() => events.length).toBe(1);
    expect(events[0]).toMatchObject({
      event: 'theme',
      kind: 'custom',
      name: 'custom',
      via: 'hex',
      page: 'about',
      theme: 'custom',
    });
  });

  test('a custom theme still counts when the page is left with the picker open', async ({
    page,
  }) => {
    const events = await recordEvents(page);
    await page.goto('/about');
    await page.click('#theme-button');
    await page.fill('#seed-bg', '#112233');
    await expect(page.locator('html')).toHaveAttribute('data-theme', /^112233-/);
    // Playwright sees no request Chromium sends while unloading, so the page fires pagehide itself.
    await page.evaluate(() => dispatchEvent(new PageTransitionEvent('pagehide')));
    await expect.poll(() => events.length).toBe(1);
    expect(events[0]).toMatchObject({ event: 'theme', kind: 'custom', via: 'hex', page: 'about' });
  });

  test('Back to yours names the family the visitor follows', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    const events = await recordEvents(page);
    await page.goto('/about?t=nord');
    await page.click('[data-action=drop-shared]');
    await expect.poll(() => events.length).toBe(1);
    expect(events[0]).toMatchObject({
      event: 'theme',
      kind: 'drop',
      name: 'fireproof',
      via: 'shared',
      theme: 'flexoki-light',
      source: 'system',
    });
  });

  test('Copy link is a share event', async ({ page, context, browserName }) => {
    test.skip(browserName !== 'chromium', 'clipboard permissions are Chromium-only in Playwright');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const events = await recordEvents(page);
    await page.goto('/loose-squares');
    await page.locator('#main [data-action=copy-link]').click();
    await expect.poll(() => events.length).toBe(1);
    expect(events[0]).toMatchObject({ event: 'share', page: 'loose-squares' });
  });

  test('nothing is sent under Global Privacy Control', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(Navigator.prototype, 'globalPrivacyControl', { get: () => true });
      const send = navigator.sendBeacon.bind(navigator);
      (window as unknown as { beacons: number }).beacons = 0;
      navigator.sendBeacon = (...args) => {
        (window as unknown as { beacons: number }).beacons++;
        return send(...args);
      };
    });
    const sent: string[] = [];
    page.on('request', (r) => {
      if (new URL(r.url()).pathname === '/e') sent.push(r.method());
    });
    await page.goto('/');
    await page.locator('.themes button[data-preset=nord]').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'nord');
    expect(await page.evaluate(() => (window as unknown as { beacons: number }).beacons)).toBe(0);
    expect(sent).toEqual([]);
  });
});
