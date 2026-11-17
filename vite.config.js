import { defineConfig } from 'vite';
import fs from 'node:fs';
import path from 'node:path';

// En desarrollo sirve ./datos_locales/ en /datos/ para probar sin red.
const datosLocales = () => ({
  name: 'datos-locales',
  configureServer(server) {
    server.middlewares.use('/datos/', (req, res, next) => {
      const f = path.join('datos_locales', decodeURIComponent((req.url || '').split('?')[0]));
      if (!fs.existsSync(f) || !fs.statSync(f).isFile()) return next();
      res.setHeader('Access-Control-Allow-Origin', '*');
      fs.createReadStream(f).pipe(res);
    });
  },
});

export default defineConfig({ base: './', plugins: [datosLocales()] });
