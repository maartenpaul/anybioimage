// anybioimage/frontend/viewer/build.config.mjs
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

await build({
  entryPoints: [resolve(__dirname, 'src/entry.js')],
  outfile: resolve(__dirname, 'dist/viewer-bundle.js'),
  bundle: true,
  format: 'esm',
  target: 'es2020',
  platform: 'browser',
  minify: true,
  sourcemap: false,
  loader: { '.js': 'jsx', '.jsx': 'jsx' },
  jsx: 'automatic',
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
});
