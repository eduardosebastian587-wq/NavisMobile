// Descarga a herramientas/<destino>/ los archivos de una carpeta de Drive (sin _respaldos). Uso: node tools/bajar_herramientas.mjs <idCarpeta> <destino>
import fs from 'node:fs'; import path from 'node:path';
const [id, destino] = process.argv.slice(2);
const html = await (await fetch(`https://drive.google.com/embeddedfolderview?id=${id}`)).text();
fs.mkdirSync(destino, {recursive: true});
for (const m of html.matchAll(/id="entry-([\w-]+)"[\s\S]*?class="flip-entry-title">([^<]+)</g)) {
  const nombre = m[2].replace(/&amp;/g, '&').trim(); if (nombre.startsWith('_respaldos')) continue;
  const r = await fetch(`https://drive.usercontent.google.com/download?id=${m[1]}&export=download&confirm=t`);
  const b = Buffer.from(await r.arrayBuffer()); const t = r.headers.get('content-type') || '';
  if (!r.ok || /text\/html/.test(t) && b.length < 5000 && !/\.html?$/i.test(nombre)) { console.log('omitido (carpeta o error):', nombre); continue; }
  fs.writeFileSync(path.join(destino, nombre), b); console.log(nombre, b.length);
}
