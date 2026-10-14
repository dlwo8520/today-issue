import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  base: process.env.VITE_BASE_PATH || './',
  publicDir: process.env.PUBLIC_ASSET_DIR || 'public',
  plugins: [react(), tailwindcss()],
  server: {
    watch: {
      usePolling: process.platform === 'win32',
      ignored: ['**/data/raw/**', '**/data/debug/**', '**/data/cache/**', '**/data/reports/**',
        '**/public/data/latest.json', '**/public/data/status.json'],
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
});
