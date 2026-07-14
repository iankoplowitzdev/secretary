/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // e2e/ holds Playwright specs (npm run test:e2e), not Vitest ones --
    // they use incompatible test/expect APIs.
    exclude: ['**/node_modules/**', 'e2e/**'],
  },
})
