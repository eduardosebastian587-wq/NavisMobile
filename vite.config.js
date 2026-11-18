import {defineConfig} from 'vite';
import fs from 'node:fs';
import path from 'node:path';

// Los modelos viven en modelos_movil/ (no en public/): se sirven en desarrollo y se copian a dist/modelos al compilar.
const modelos = path.resolve('modelos_movil');
const tipos = {'.glb': 'model/gltf-binary', '.json': 'application/json'};
export default defineConfig({
  base: './',
  plugins: [{
    name: 'modelos-movil',
    configureServer(s) {
      s.middlewares.use('/modelos', (req, res, next) => {
        const f = path.join(modelos, decodeURIComponent((req.url || '').split('?')[0]));
        if (!f.startsWith(modelos) || !fs.existsSync(f) || !fs.statSync(f).isFile()) return next();
        res.setHeader('Content-Type', tipos[path.extname(f)] || 'application/octet-stream');
        fs.createReadStream(f).pipe(res);
      });
    },
    closeBundle() {
      const dest = path.resolve('dist/modelos'); fs.mkdirSync(dest, {recursive: true});
      for (const n of fs.readdirSync(modelos)) fs.copyFileSync(path.join(modelos, n), path.join(dest, n));
    },
  }],
  build: {chunkSizeWarningLimit: 1500},
});
