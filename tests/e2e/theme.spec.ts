import type { Page } from '@playwright/test';
import { expect, test } from './test';

/** The theme token saved in localStorage, or null. */
const saved = (page: Page) => page.evaluate(() => localStorage.getItem('walldye.theme'));

/** Text of the SVG each index plate currently shows. */
async function plateSvgs(page: Page): Promise<string[]> {
  return page.evaluate(async () => {
    const imgs = [...document.querySelectorAll<HTMLImageElement>('.grid .plate > img')];
    return Promise.all(imgs.map(async (img) => (await fetch(img.src)).text()));
  });
}

test.describe('without JavaScript', () => {
  test.use({ javaScriptEnabled: false, colorScheme: 'light' });

  test('controls that need it are left out, and plates keep the template ground', async ({
    page,
  }) => {
    await page.goto('/');
    await expect(page.locator('#theme-button')).toBeHidden();
    await expect(page.locator('#facets')).toBeHidden();
    // Every plate carries its <noscript> template.
    const plates = await page.locator('.grid > li').count();
    expect(plates).toBeGreaterThan(0);
    await expect(page.locator('.grid .plate img')).toHaveCount(plates);
    expect(
      await page
        .locator('.grid .plate')
        .first()
        .evaluate((el) => getComputedStyle(el).backgroundColor),
    ).toBe('rgb(28, 27, 26)');
    await page.goto('/schotter');
    await expect(page.locator('.controls')).toBeHidden();
    await expect(page.locator('[data-action=copy-source]')).toBeHidden();
  });
});

test.describe('theme', () => {
  test.use({ colorScheme: 'dark' });

  test('a preset recolors the index and is saved', async ({ page }) => {
    await page.goto('/');
    // Plates near the view load; fireproof shows the untouched templates.
    await expect(page.locator('.grid .plate > img').first()).toHaveAttribute(
      'src',
      /^\/t\/[0-9a-f]{12}\.svg$/,
    );

    await page.click('#theme-button');
    await expect(page.locator('#theme-button')).toHaveAttribute('aria-expanded', 'true');
    await page.click('#picker button[data-preset=nord]');

    await expect(page.locator('html')).toHaveAttribute('style', /--seed-bg: #2E3440/);
    await expect(page.locator('#picker button[data-preset=nord]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await expect(page.locator('#picker button[data-preset=fireproof]')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await expect(page.locator('[data-theme-name]')).toHaveText('nord');
    await expect(page.locator('#theme-button')).toHaveAttribute(
      'aria-label',
      'nord theme: background #2E3440, foreground #ECEFF4, accent #88C0D0',
    );
    await expect(page.locator('#seed-bg')).toHaveValue('#2E3440');
    await expect
      .poll(async () =>
        (
          await page
            .locator('.grid .plate > img')
            .evaluateAll((imgs) => imgs.map((i) => i.getAttribute('src')))
        ).every((s) => s?.startsWith('blob:')),
      )
      .toBe(true);
    for (const svg of await plateSvgs(page)) {
      expect(svg).toContain('#2E3440');
      expect(svg).not.toContain('#1C1B1A');
    }
    expect(await saved(page)).toBe('nord');

    await page.reload();
    await expect(page.locator('[data-theme-name]')).toHaveText('nord');
  });

  test('a family follows the system scheme, and the default family goes back to nothing saved', async ({
    page,
  }) => {
    await page.goto('/');
    await page.click('#theme-button');
    const family = page.locator('#picker button[data-family=rose-pine]');
    await family.click();
    await expect(page.locator('[data-theme-name]')).toHaveText('rose-pine');
    await expect(family).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#picker button[data-preset=rose-pine]')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(await saved(page)).toBe('pair:rose-pine,rose-pine-dawn');
    await page.emulateMedia({ colorScheme: 'light' });
    await expect(page.locator('[data-theme-name]')).toHaveText('rose-pine-dawn');

    // A swatch fixes one theme of the family, whatever the system prefers.
    await page.click('#picker button[data-preset=rose-pine]');
    await expect(page.locator('[data-theme-name]')).toHaveText('rose-pine');
    await expect(family).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('#picker button[data-preset=rose-pine]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(await saved(page)).toBe('rose-pine');

    await page.click('#picker button[data-family=fireproof]');
    await expect(page.locator('[data-theme-name]')).toHaveText('flexoki-light');
    expect(await saved(page)).toBeNull();
    await page.reload();
    await expect(page.locator('[data-theme-name]')).toHaveText('flexoki-light');
  });

  test('the system scheme is followed while nothing is saved', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('html')).toHaveAttribute('data-regime', 'dark');
    await page.emulateMedia({ colorScheme: 'light' });
    await expect(page.locator('html')).toHaveAttribute('data-regime', 'light');
    await expect(page.locator('[data-theme-name]')).toHaveText('flexoki-light');
  });

  test('the color fields validate, apply after a pause and revert on Escape', async ({ page }) => {
    await page.goto('/');
    await page.click('#theme-button');
    const accent = page.locator('#seed-accent');

    // A field is marked once the visitor leaves it.
    await accent.fill('#CF6A4');
    await page.waitForTimeout(400);
    await expect(accent).not.toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('#seed-msg')).toBeHidden();
    await page.locator('#seed-bg').focus();
    await expect(accent).toHaveAttribute('aria-invalid', 'true');
    await expect(accent).toHaveAttribute('aria-describedby', 'seed-msg');
    await expect(page.locator('#seed-msg')).toBeVisible();
    await expect(page.locator('#seed-msg')).toHaveText('Use a hex color, like #CF6A4C.');
    expect(await saved(page)).toBeNull();

    await accent.fill('0af');
    await expect(accent).not.toHaveAttribute('aria-invalid', 'true');
    await expect(page.locator('#seed-msg')).toBeHidden();
    await expect(page.locator('html')).toHaveAttribute('style', /--seed-accent: #00AAFF/);
    await expect(page.locator('[data-theme-name]')).toHaveText('custom');
    expect(await saved(page)).toBe('1c1b1a-dad8ce-00aaff');

    // An unapplied edit is dropped by Escape, which also closes the picker. (An incomplete value
    // never applies, so the check does not race the debounce.)
    await accent.fill('#12');
    await page.keyboard.press('Escape');
    await expect(page.locator('#picker')).toBeHidden();
    await expect(page.locator('html')).toHaveAttribute('style', /--seed-accent: #00AAFF/);
    await page.click('#theme-button');
    await expect(accent).toHaveValue('#00AAFF');
  });

  test('close background and foreground colors get a warning', async ({ page }) => {
    await page.goto('/');
    await page.click('#theme-button');
    await page.locator('#seed-fg').fill('#3A3836');
    await expect(page.locator('#faint-msg')).toBeVisible();
    await expect(page.locator('#seed-bg')).toHaveAttribute('aria-describedby', 'faint-msg');
    await expect(page.locator('#seed-fg')).toHaveAttribute('aria-describedby', 'faint-msg');
    await expect(page.locator('#seed-accent')).not.toHaveAttribute('aria-describedby', /./);
  });

  test('an accent close to the background or foreground gets a warning', async ({ page }) => {
    await page.goto('/');
    await page.click('#theme-button');
    const accent = page.locator('#seed-accent');
    await accent.fill('#D6D2C6');
    await expect(page.locator('#accent-fg-msg')).toBeVisible();
    await expect(accent).toHaveAttribute('aria-describedby', 'accent-fg-msg');
    await accent.fill('#24221F');
    await expect(page.locator('#accent-fg-msg')).toBeHidden();
    await expect(page.locator('#accent-bg-msg')).toBeVisible();
    await expect(accent).toHaveAttribute('aria-describedby', 'accent-bg-msg');
    await accent.fill('#CF6A4C');
    await expect(page.locator('#accent-bg-msg')).toBeHidden();
    await expect(accent).not.toHaveAttribute('aria-describedby', /./);
  });

  test('a swatch opens a color picker whose choice fills its field', async ({ page }) => {
    await page.goto('/');
    await page.click('#theme-button');
    const pick = page.locator('#picker .hexfield .chip input[type=color]').first();
    await expect(pick).toHaveValue('#1c1b1a');
    await pick.fill('#102030');
    await expect(page.locator('#seed-bg')).toHaveValue('#102030');
    await expect(page.locator('html')).toHaveAttribute('style', /--seed-bg: #102030/);
    expect(await saved(page)).toBe('102030-dad8ce-cf6a4c');
    // Typing a color moves the picker with it.
    await page.locator('#seed-accent').fill('#0AF');
    await expect(page.locator('#picker .hexfield .chip input[type=color]').last()).toHaveValue(
      '#00aaff',
    );
  });

  test('a pasted theme fills all three fields', async ({ page, browserName }) => {
    test.skip(browserName === 'firefox', 'Firefox empties clipboardData on synthetic paste events');
    await page.goto('/');
    await page.click('#theme-button');
    await page.locator('#seed-bg').focus();
    await page.evaluate(() => {
      const data = new DataTransfer();
      data.setData('text', '282828, ebdbb2, fe8019');
      document
        .getElementById('seed-bg')!
        .dispatchEvent(
          new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }),
        );
    });
    await expect(page.locator('#seed-bg')).toHaveValue('#282828');
    await expect(page.locator('#seed-fg')).toHaveValue('#EBDBB2');
    await expect(page.locator('#seed-accent')).toHaveValue('#FE8019');
    await expect(page.locator('[data-theme-name]')).toHaveText('gruvbox-dark');
  });

  test('a shared link applies for the session until kept or dropped', async ({ page }) => {
    await page.goto('/about?t=nord');
    expect(new URL(page.url()).search).toBe('');
    await expect(page.locator('[data-theme-name]')).toHaveText('nord');
    await expect(page.locator('#shared')).toBeVisible();
    expect(await saved(page)).toBeNull();

    // The session keeps the shared theme across pages.
    await page.click('.nav a[href="/"]');
    await expect(page.locator('[data-theme-name]')).toHaveText('nord');
    await expect(page.locator('#shared')).toBeVisible();

    await page.click('[data-action=drop-shared]');
    await expect(page.locator('[data-theme-name]')).toHaveText('fireproof');
    await expect(page.locator('#shared')).toBeHidden();

    await page.goto('/?t=0a0a0a-f0f0f0-ff0000');
    await expect(page.locator('#shared')).toBeVisible();
    await page.click('[data-action=keep-shared]');
    await expect(page.locator('#shared')).toBeHidden();
    expect(await saved(page)).toBe('0a0a0a-f0f0f0-ff0000');
    await expect(page.locator('[data-theme-name]')).toHaveText('custom');
  });

  test('the shared-theme line follows a system scheme change', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    // Equal to the visitor's own theme under a light system, so there is nothing to offer.
    await page.goto('/?t=flexoki-light');
    await expect(page.locator('#shared')).toBeHidden();
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(page.locator('#shared')).toBeVisible();
    await expect(page.locator('[data-theme-name]')).toHaveText('flexoki-light');
    await page.click('[data-action=drop-shared]');
    await expect(page.locator('[data-theme-name]')).toHaveText('fireproof');
  });

  test('a shared link still applies when the session cannot be stored', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, 'sessionStorage', {
        get() {
          throw new DOMException('denied', 'SecurityError');
        },
      });
    });
    await page.goto('/?t=nord');
    expect(new URL(page.url()).search).toBe('');
    await expect(page.locator('[data-theme-name]')).toHaveText('nord');
    await expect(page.locator('#shared')).toBeVisible();
  });

  test('an invalid shared theme is ignored and stripped', async ({ page }) => {
    await page.goto('/?t=nope&q=moon');
    expect(new URL(page.url()).searchParams.has('t')).toBe(false);
    await expect(page.locator('#shared')).toBeHidden();
    await expect(page.locator('[data-theme-name]')).toHaveText('fireproof');
  });

  test('Copy link includes the theme', async ({ page, context, browserName }) => {
    test.skip(browserName !== 'chromium', 'clipboard permissions are Chromium-only in Playwright');
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.goto('/?technique=drafting');
    await page.click('#theme-button');
    await page.click('#picker button[data-preset=rose-pine]');
    await page.click('#picker [data-action=copy-link]');
    await expect(page.locator('#picker [data-action=copy-link]')).toHaveText('Link copied');
    const text = await page.evaluate(() => navigator.clipboard.readText());
    const url = new URL(text);
    expect(url.searchParams.get('t')).toBe('rose-pine');
    expect(url.searchParams.get('technique')).toBe('drafting');
  });
});

/** Pastes `text` into `selector` as the clipboard would. */
const paste = (page: Page, selector: string, text: string) =>
  page.locator(selector).evaluate((el, t) => {
    const data = new DataTransfer();
    data.setData('text/plain', t);
    el.dispatchEvent(
      new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }),
    );
  }, text);

test.describe('colors', () => {
  test.use({ colorScheme: 'dark', viewport: { width: 1440, height: 1000 } });

  test('the row over the grid applies and saves a preset', async ({ page }) => {
    await page.goto('/');
    const nord = page.locator('.themes button[data-preset=nord]');
    await expect(page.locator('.themes button[data-family=fireproof]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await nord.click();
    await expect(page.locator('.themes button[data-family=fireproof]')).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'nord');
    await expect(nord).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#picker button[data-preset=nord]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(await page.evaluate(() => localStorage.getItem('walldye.theme'))).toBe('nord');
  });

  test('a family in the row shows and picks its theme for the system scheme', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/');
    const gruvbox = page.locator('.themes button[data-family=gruvbox]');
    await expect(gruvbox.locator('.for-light')).toBeVisible();
    await expect(gruvbox.locator('.for-dark')).toBeHidden();
    await gruvbox.click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'gruvbox-light');
    await expect(gruvbox).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#picker button[data-family=gruvbox]')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(gruvbox.locator('.for-dark')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'gruvbox-dark');
  });

  test('a pasted terminal theme fills the colors', async ({ page, browserName }) => {
    test.skip(browserName === 'firefox', 'Firefox empties clipboardData on synthetic paste events');
    await page.goto('/about');
    await page.click('#theme-button');
    await paste(page, '#theme-import', 'hello');
    await expect(page.locator('#import-msg')).toBeVisible();
    await paste(
      page,
      '#theme-import',
      'background #101820\nforeground #F0F0E0\ncolor1 #E04040\ncolor4 #202830',
    );
    await expect(page.locator('#import-msg')).toBeHidden();
    await expect(page.locator('#seed-bg')).toHaveValue('#101820');
    await expect(page.locator('#seed-accent')).toHaveValue('#E04040');
    await expect(page.locator('html')).toHaveAttribute('data-theme', '101820-f0f0e0-e04040');
  });
});
