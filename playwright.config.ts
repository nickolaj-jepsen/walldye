import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.E2E_PORT ?? 4399);
const PERF = '**/perf.spec.ts';

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
    { name: 'chromium', use: { ...devices['Desktop Chrome'] }, testIgnore: PERF },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] }, testIgnore: PERF },
    { name: 'webkit', use: { ...devices['Desktop Safari'] }, testIgnore: PERF },
    // Timing runs alone, after the rest; `--project=perf --no-deps` runs it by itself. No trace: recording
    // one snapshots the whole index in the page on every action, a long task the site does not make.
    { name: 'perf', use: { ...devices['Desktop Chrome'], trace: 'off' }, testMatch: PERF, dependencies: ['chromium', 'firefox', 'webkit'] },
  ],
  webServer: {
    command: `${process.env.E2E_SKIP_BUILD ? '' : 'pnpm astro build && '}pnpm astro preview --ignore-lock --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 300_000,
  },
});
