// Descarga un archivo de una carpeta de Google Drive compartida por enlace (sin clave ni login).
// Busca por nombre en la carpeta y sus subcarpetas (gana la primera coincidencia, la más superficial),
// o descarga directo si se pasa un id o un enlace de Drive.
// Uso: node herramientas/drive_descargar.mjs --archivo area1313.nmraw --carpeta <idCarpeta> --destino trabajo/
//      node herramientas/drive_descargar.mjs --archivo https://drive.google.com/file/d/<id>/view --destino trabajo/x.fbx
// Imprime la ruta local descargada. Con --tambien ".piezas.json" baja además <archivo>.piezas.json.
import fs from 'node:fs';
import path from 'node:path';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';

const arg = (n, d) => { const k = process.argv.indexOf('--' + n); return k > 0 ? process.argv[k + 1] : d; };
const UA = {'User-Agent': 'Mozilla/5.0 (navismobile)'};

async function listar(idCarpeta) {
  const r = await fetch(`https://drive.google.com/embeddedfolderview?id=${idCarpeta}`, {headers: UA});
  if (!r.ok) throw new Error(`No pude listar la carpeta ${idCarpeta} (HTTP ${r.status}): ¿está compartida por enlace?`);
  const html = await r.text();
  const re = /<div class="flip-entry" id="entry-([^"]+)"[\s\S]*?<a href="([^"]+)"[\s\S]*?flip-entry-title">([^<]*)</g;
  const dec = s => s.replace(/&amp;/g, '&').replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
  return [...html.matchAll(re)].map(m => ({id: m[1], carpeta: m[2].includes('/folders/'), nombre: dec(m[3])}));
}

export async function buscar(idCarpeta, nombre, profundidad = 6) {
  let nivel = [idCarpeta];
  for (let p = 0; p <= profundidad && nivel.length; p++) {
    const siguiente = [];
    for (const c of nivel) {
      for (const e of await listar(c)) {
        if (!e.carpeta && e.nombre === nombre) return e.id;
        if (e.carpeta && !e.nombre.startsWith('_por_borrar')) siguiente.push(e.id);
      }
    }
    nivel = siguiente;
  }
  throw new Error(`No encontré "${nombre}" en la carpeta ${idCarpeta}`);
}

export async function descargar(id, destino) {
  const url = `https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`;
  const r = await fetch(url, {headers: UA});
  if (!r.ok) throw new Error(`Descarga ${id}: HTTP ${r.status}`);
  if ((r.headers.get('content-type') || '').startsWith('text/html')) throw new Error(`Descarga ${id}: Drive devolvió una página, no el archivo (¿compartido por enlace?)`);
  fs.mkdirSync(path.dirname(path.resolve(destino)), {recursive: true});
  await pipeline(Readable.fromWeb(r.body), fs.createWriteStream(destino));
  return destino;
}

function idDeEnlace(s) {
  const m = /\/d\/([\w-]{20,})/.exec(s) || /[?&]id=([\w-]{20,})/.exec(s);
  return m ? m[1] : (/^[\w-]{25,}$/.test(s) && !s.includes('.') ? s : null);
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
  const archivo = arg('archivo'), carpeta = arg('carpeta'), destino = arg('destino', '.');
  if (!archivo) throw new Error('Falta --archivo');
  const directo = idDeEnlace(archivo);
  const nombre = directo ? (arg('nombre') || `${directo}.bin`) : archivo;
  const id = directo || await buscar(carpeta, archivo);
  const ruta = destino.endsWith('/') || fs.existsSync(destino) && fs.statSync(destino).isDirectory() ? path.join(destino, nombre) : destino;
  const t0 = Date.now();
  await descargar(id, ruta);
  console.error(`Descargado ${nombre} (${(fs.statSync(ruta).size / 1e6).toFixed(1)} MB, ${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  const extra = arg('tambien');
  if (extra && !directo) await descargar(await buscar(carpeta, archivo + extra), ruta + extra);
  console.log(ruta);
}
