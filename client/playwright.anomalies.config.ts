import { defineConfig, devices } from '@playwright/test'
declare const process: { env: Record<string, string | undefined> }
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:58081'
const target = new URL(baseURL)
if (target.protocol !== 'http:' || target.hostname !== '127.0.0.1' || target.port !== '58081' || target.username || target.password || target.pathname !== '/') throw new Error('M9 requires the isolated loopback target.')
for (const role of ['ADMIN', 'WAREHOUSE', 'CLIENT']) for (const field of ['EMAIL', 'PASSWORD']) if (!process.env['E2E_' + role + '_' + field]) throw new Error('Explicit isolated credentials required.')
export default defineConfig({
  testDir: './e2e-anomalies', timeout: 120_000, workers: 1, fullyParallel: false, retries: 0,
  reporter: [['list']], outputDir: 'test-results-anomalies',
  use: { baseURL, trace: 'off', screenshot: 'off', video: 'off' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
})
