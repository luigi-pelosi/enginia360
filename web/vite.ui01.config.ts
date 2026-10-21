// Opt-in UI01.a prototype build only. The default public bootstrap build uses vite.config.ts.
import { defineConfig } from 'vite';
export default defineConfig({
    build: { outDir: 'dist-ui01', emptyOutDir: true, rollupOptions: { input: 'ui01.html' } },
});
