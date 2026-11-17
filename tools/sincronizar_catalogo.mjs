// Actualiza IDs y tamaños de public/catalogo.json recorriendo las carpetas de Drive (sin clave de API).
// Uso: node tools/sincronizar_catalogo.mjs
import fs from 'node:fs';
const RUTA = new URL('../public/catalogo.json', import.meta.url);
const cat = JSON.parse(fs.readFileSync(RUTA, 'utf8'));
const url = id => `https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`;

async function listar(carpeta, vistas = new Set()) {
  if (vistas.has(carpeta)) return []; vistas.add(carpeta);
  const r = await fetch(`https://drive.google.com/embeddedfolderview?id=${carpeta}`);
  if (!r.ok) throw new Error(`carpeta ${carpeta}: HTTP ${r.status}`);
  const html = await r.text(), out = [];
  for (const m of html.matchAll(/id="entry-([\w-]+)"[\s\S]*?class="flip-entry-title">([^<]+)</g))
    out.push({id: m[1], nombre: m[2].replace(/&amp;/g, '&').trim()});
  return out;
}
async function bytes(id) {
  try { const r = await fetch(url(id), {method: 'HEAD'}); return +r.headers.get('content-length') || 0; } catch { return 0; }
}
function archivos(escena) {
  const a = [];
  for (const m of escena.modelos || []) a.push(m.archivo);
  if (escena.escena) a.push(escena.escena);
  if (escena.correas) a.push(escena.correas);
  if (escena.animaciones) a.push(escena.animaciones);
  if (escena.equipos) a.push(escena.equipos.json, escena.equipos.bin);
  for (const r of escena.recorridos || []) a.push(r.archivo);
  for (const c of escena.capas_extra || []) a.push(c.archivo);
  return a;
}

let cambios = 0, nuevos = [];
for (const car of cat.carpetas || []) {
  const escena = cat.escenas.find(e => e.id === car.escena); if (!escena) continue;
  let lista; try { lista = await listar(car.id); } catch (e) { console.warn('⚠', e.message); continue; }
  const conocidos = archivos(escena);
  for (const it of lista) {
    const a = conocidos.find(x => x.nombre === it.nombre);
    if (a) {
      const b = await bytes(it.id);
      if (a.drive !== it.id || (b && a.bytes !== b)) { console.log(`~ ${it.nombre}: ${a.drive} → ${it.id}, ${a.bytes} → ${b}`); a.drive = it.id; if (b) a.bytes = b; cambios++; }
    } else if (/_web.*\.glb$|recorrido.*\.json$/i.test(it.nombre)) nuevos.push(`${escena.id}: ${it.nombre} (${it.id})`);
  }
}
if (cambios) fs.writeFileSync(RUTA, JSON.stringify(cat, null, 1) + '\n');
console.log(cambios ? `${cambios} entrada(s) actualizada(s).` : 'Catálogo al día.');
if (nuevos.length) console.log('Archivos nuevos que podría añadir a mano al catálogo:\n  ' + nuevos.join('\n  '));
