import { defineConfig } from '@playwright/test'
import base from './playwright.config'

declare const process: { env: Record<string, string | undefined> }
if (process.env.E2E_BASE_URL !== 'http://127.0.0.1:58081') {
  throw new Error('Explicit isolated M8 loopback origin required.')
}
export default defineConfig(base, {
  testDir: './e2e-cold-start',
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:58081', trace: 'off', screenshot: 'off', video: 'off' },
})
