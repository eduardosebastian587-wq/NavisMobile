// Sirve la carpeta areas/ por la red local para que el teléfono descargue las áreas sin internet.
// Uso: node herramientas/servir_areas.mjs [--puerto 8090]
// En la app: Escenas › "IP del PC" = la dirección que muestra este script › Usar PC.
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'areas');
const i = process.argv.indexOf('--puerto');
const PUERTO = i > 0 ? +process.argv[i + 1] : 8090;
const tipos = {'.glb': 'model/gltf-binary', '.json': 'application/json'};

http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', '*');
  if (req.method === 'OPTIONS') return res.end();
  const f = path.join(raiz, decodeURIComponent((req.url || '/').split('?')[0]));
  if (!f.startsWith(raiz) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.statusCode = 404; return res.end('no existe'); }
  const st = fs.statSync(f);
  res.setHeader('Content-Type', tipos[path.extname(f)] || 'application/octet-stream');
  res.setHeader('Content-Length', st.size);
  res.setHeader('Cache-Control', 'no-cache');
  if (req.method === 'HEAD') return res.end();
  fs.createReadStream(f).pipe(res);
  console.log(new Date().toLocaleTimeString(), req.socket.remoteAddress, req.url.split('?')[0]);
}).listen(PUERTO, '0.0.0.0', () => {
  const ips = Object.values(os.networkInterfaces()).flat().filter(a => a && a.family === 'IPv4' && !a.internal).map(a => a.address);
  console.log(`Sirviendo ${raiz}`);
  console.log('En la app escriba una de estas direcciones en "IP del PC":');
  for (const ip of ips) console.log(`   ${ip}:${PUERTO}`);
});
