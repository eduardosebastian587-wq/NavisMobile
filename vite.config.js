import {defineConfig} from 'vite';
import fs from 'node:fs';
import path from 'node:path';

// Las áreas (GLB + JSON + catalogo.json) viven en areas/ y NO van dentro de la APK: la app las descarga
// desde el PC por Wi-Fi (herramientas/servir_areas.mjs) o desde GitHub (raw). En desarrollo se sirven en /areas.
// Al compilar solo se incluye una copia del catálogo con "base" en GitHub, como respaldo sin conexión.
const areas = path.resolve('areas');
const GITHUB = 'https://raw.githubusercontent.com/eduardosebastian587-wq/NavisMobile/main/areas/catalogo.json';
const tipos = {'.glb': 'model/gltf-binary', '.json': 'application/json'};
export default defineConfig({
  base: './',
  plugins: [{
    name: 'areas',
    configureServer(s) {
      s.middlewares.use('/areas', (req, res, next) => {
        const f = path.join(areas, decodeURIComponent((req.url || '').split('?')[0]));
        if (!f.startsWith(areas) || !fs.existsSync(f) || !fs.statSync(f).isFile()) return next();
        res.setHeader('Content-Type', tipos[path.extname(f)] || 'application/octet-stream');
        fs.createReadStream(f).pipe(res);
      });
    },
    closeBundle() {
      const c = JSON.parse(fs.readFileSync(path.join(areas, 'catalogo.json'), 'utf8'));
      fs.writeFileSync(path.resolve('dist/catalogo.json'), JSON.stringify({...c, base: GITHUB}));
    },
  }],
  build: {chunkSizeWarningLimit: 1500},
});
