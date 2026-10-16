import { defineConfig, devices } from '@playwright/test'
declare const process: { env: Record<string, string | undefined> }
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:58080'
const target = new URL(baseURL)
if (target.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(target.hostname) || !['58080', '58081', '18081'].includes(target.port) || target.username || target.password) {
  throw new Error('E2E writes require the explicitly isolated loopback web port.')
}

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  use: {
    baseURL,
    // Real authentication is exercised; do not capture bearer/password payloads.
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
