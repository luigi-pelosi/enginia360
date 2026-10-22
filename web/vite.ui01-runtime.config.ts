import { defineConfig } from 'vite';
export default defineConfig({ build: { outDir: 'dist-ui01-runtime', rollupOptions: { input: 'ui01-runtime.html' } } });
