import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
  },
  // Launches the real Vite dev server, which picks up .env.local
  // (VITE_FUNCTION_URL) the same way `npm run dev` does -- this is what
  // makes the test exercise the real deployed backend, not the mock.
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
