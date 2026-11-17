// Uso: node tools/sincronizar_catalogo.mjs
// Lista cada carpeta de Drive (embeddedfolderview), actualiza IDs por nombre de archivo
// y avisa de archivos *_web*.glb / *recorrido*.json que no estén en el catálogo.
import fs from 'node:fs';

const RUTA = new URL('../public/catalogo.json', import.meta.url);
const cat = JSON.parse(fs.readFileSync(RUTA, 'utf8'));

async function listar(idCarpeta) {
  const r = await fetch(`https://drive.google.com/embeddedfolderview?id=${idCarpeta}`);
  if (!r.ok) throw new Error(`Carpeta ${idCarpeta}: HTTP ${r.status}`);
  const html = await r.text();
  const ids = [...html.matchAll(/id="entry-([\w-]+)"/g)].map((m) => m[1]);
  const nombres = [...html.matchAll(/class="flip-entry-title">([^<]+)</g)].map((m) => m[1].trim());
  return ids.map((id, i) => ({ id, nombre: nombres[i] }));
}

async function bytesDe(id) {
  const r = await fetch(`https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`, { method: 'HEAD' });
  return Number(r.headers.get('content-length')) || undefined;
}

function* archivos(escena) {
  for (const m of escena.modelos || []) yield m.archivo;
  for (const x of [escena.escena, escena.correas, escena.animaciones, escena.equipos?.json, escena.equipos?.bin]) if (x) yield x;
  for (const x of escena.recorridos || []) yield x;
  for (const x of escena.capas_extra || []) yield x.archivo;
}

for (const esc of cat.escenas) {
  const porNombre = new Map();
  for (const c of esc.carpetas || []) for (const e of await listar(c)) porNombre.set(e.nombre, e.id);
  const conocidos = new Set();
  for (const a of archivos(esc)) {
    conocidos.add(a.nombre);
    if (!a.drive) continue;
    const id = porNombre.get(a.nombre);
    if (!id) { console.warn(`[${esc.id}] no está en Drive: ${a.nombre}`); continue; }
    if (id !== a.drive) { console.log(`[${esc.id}] ID nuevo para ${a.nombre}`); a.drive = id; }
    const b = await bytesDe(id);
    if (b && b !== a.bytes) { console.log(`[${esc.id}] bytes ${a.nombre}: ${a.bytes} → ${b}`); a.bytes = b; }
  }
  for (const n of porNombre.keys())
    if (/_web.*\.glb$|recorrido.*\.json$/.test(n) && !conocidos.has(n)) console.log(`[${esc.id}] NUEVO en Drive: ${n}`);
}
fs.writeFileSync(RUTA, JSON.stringify(cat, null, 2) + '\n');
console.log('Catálogo sincronizado.');
