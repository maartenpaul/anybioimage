// anybioimage/frontend/viv/build.config.mjs
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

await build({
  entryPoints: [resolve(__dirname, 'src/entry.js')],
  outfile: resolve(__dirname, 'dist/viv-bundle.js'),
  bundle: true,
  format: 'esm',
  target: 'es2020',
  platform: 'browser',
  minify: true,
  sourcemap: false,
  loader: {
    '.js': 'jsx',
    '.jsx': 'jsx',
    // Canvas2D ESM is a raw ESM module source — inline as text and eval via Blob URL in the fallback path.
    '.canvas2d.js': 'text',
  },
  jsx: 'automatic',
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  logLevel: 'info',
});
