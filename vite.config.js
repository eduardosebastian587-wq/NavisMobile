import {defineConfig} from 'vite';
import fs from 'node:fs';
import path from 'node:path';

// En desarrollo, sirve la carpeta local «datos_locales» (y «datos») en /datos/<nombre> para probar sin red.
const datosLocales = () => ({
  name: 'datos-locales',
  configureServer(server) {
    server.middlewares.use('/datos/', (req, res, next) => {
      const nombre = decodeURIComponent((req.url || '').split('?')[0]).replace(/^\/+/, '');
      for (const dir of ['datos_locales', 'datos']) {
        const f = path.resolve(dir, nombre);
        if (f.startsWith(path.resolve(dir)) && fs.existsSync(f) && fs.statSync(f).isFile()) {
          res.setHeader('Content-Type', 'application/octet-stream');
          res.setHeader('Content-Length', fs.statSync(f).size);
          return fs.createReadStream(f).pipe(res);
        }
      }
      next();
    });
  }
});

export default defineConfig({base: './', plugins: [datosLocales()], build: {target: 'es2020', chunkSizeWarningLimit: 2000}});
