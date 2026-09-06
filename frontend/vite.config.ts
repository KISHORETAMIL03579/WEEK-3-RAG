import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/ask': 'http://127.0.0.1:5000',
      '/upload': 'http://127.0.0.1:5000',
      '/upload-cancel': 'http://127.0.0.1:5000',
      '/status': 'http://127.0.0.1:5000',
      '/load-url': 'http://127.0.0.1:5000',
      '/remove': 'http://127.0.0.1:5000',
      '/clear': 'http://127.0.0.1:5000',
      '/traces': 'http://127.0.0.1:5000',
      '/replay': 'http://127.0.0.1:5000',
      '/file': 'http://127.0.0.1:5000',
      '/eval/run': 'http://127.0.0.1:5000',
      '/eval/parse-qa-pdf': 'http://127.0.0.1:5000',
      '/orphans': 'http://127.0.0.1:5000',
      '/healthz': 'http://127.0.0.1:5000',
      '/readyz': 'http://127.0.0.1:5000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});

