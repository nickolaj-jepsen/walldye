import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.E2E_PORT ?? 4399);

/**
 * End-to-end tests against the built site (`astro build` + `astro preview`).
 *
 * On NixOS run `pnpm e2e:nix`, which points PLAYWRIGHT_BROWSERS_PATH at nixpkgs'
 * playwright-driver browsers; @playwright/test is pinned to that version.
 * Set E2E_SKIP_BUILD=1 to serve an existing dist/ without rebuilding. `--ignore-lock` keeps
 * `astro preview` in the foreground, which it otherwise leaves when it detects an agent.
 */
export default defineConfig({
  testDir: 'tests/e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: `${process.env.E2E_SKIP_BUILD ? '' : 'pnpm astro build && '}pnpm astro preview --ignore-lock --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
  },
});
