import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { environment: 'jsdom', globals: false }, server: { proxy: { '/api': 'http://localhost:8080' } } });
