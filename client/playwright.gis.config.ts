import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL
if (baseURL !== 'http://127.0.0.1:18082') throw new Error('M10 requires its exact isolated loopback URL.')
const scenario = process.env.E2E_GIS_SCENARIO
if (scenario !== 'synthetic' && scenario !== 'public') throw new Error('Select an explicit M10 GIS scenario.')
const snapshotId = process.env.E2E_GIS_SNAPSHOT_ID ?? ''
if (!/^gsv1-[0-9a-f]{64}$/.test(snapshotId)) throw new Error('Select an exact M10 snapshot ID.')
if (scenario === 'public' && snapshotId !== 'gsv1-83bb3fea3577b8821509cb5d7cbe0fd2de608965e81485045241bcdbd044f889') {
  throw new Error('Select the independently verified M10 public snapshot.')
}
for (const role of ['ADMIN', 'WAREHOUSE', 'CLIENT']) {
  for (const field of ['EMAIL', 'PASSWORD']) {
    if (!process.env['E2E_' + role + '_' + field]) throw new Error('Explicit isolated role credentials are required.')
  }
}

export default defineConfig({
  testDir: './e2e-gis',
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [['list']],
  outputDir: join(tmpdir(), 'codex-m10-gis-playwright', scenario),
  use: { baseURL, locale: 'vi-VN', trace: 'off', screenshot: 'off', video: 'off' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
})
