// Agrega o actualiza un área en areas/catalogo.json (copia GLB + JSON de elementos y calcula su huella).
// La app ve el cambio la próxima vez que abre Escenas: por Wi-Fi al instante, por GitHub tras el push.
// Uso: node herramientas/publicar_area.mjs --id area1313d --nombre "Área 1313" --glb x.glb --elementos x.json
//                                          [--descripcion "..."] [--push]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const AREAS = path.join(REPO, 'areas');

function archivo(origen, nombre) {
  const destino = path.join(AREAS, nombre);
  if (path.resolve(origen) !== destino) fs.copyFileSync(origen, destino);
  const b = fs.readFileSync(destino);
  return {ruta: nombre, nombre, bytes: b.length, sha: crypto.createHash('sha256').update(b).digest('hex').slice(0, 12)};
}

export function publicar({id, nombre, descripcion = '', glb, elementos, push = false}) {
  if (!/^[a-z0-9_-]+$/i.test(id)) throw new Error('id inválido (solo letras, números, - y _)');
  const f = path.join(AREAS, 'catalogo.json');
  const cat = JSON.parse(fs.readFileSync(f, 'utf8'));
  const modelo = {id: 'completo', nombre: 'Completo (simplificado)', archivo: archivo(glb, `${id}_movil.glb`)};
  const esc = {
    id, nombre, descripcion: descripcion || 'Toque un elemento para ver su TAG y propiedades.',
    actualizado: new Date().toISOString().slice(0, 16).replace('T', ' '),
    modelos: [modelo],
    ...(elementos ? {etiquetas: archivo(elementos, `${id}_elementos.json`)} : {}),
  };
  const i = cat.escenas.findIndex(e => e.id === id);
  if (i >= 0) cat.escenas[i] = {...cat.escenas[i], ...esc}; else cat.escenas.push(esc);
  fs.writeFileSync(f, JSON.stringify(cat, null, 2) + '\n');
  console.log(`Catálogo: ${id} ${i >= 0 ? 'actualizado' : 'agregado'} (${(modelo.archivo.bytes / 1e6).toFixed(1)} MB, sha ${modelo.archivo.sha})`);
  if (push) {
    const git = (...a) => execFileSync('git', a, {cwd: REPO, stdio: 'inherit'});
    git('add', 'areas/catalogo.json', `areas/${id}_movil.glb`, ...(elementos ? [`areas/${id}_elementos.json`] : []));
    git('commit', '-q', '-m', `Área ${id}: ${nombre} (${modelo.archivo.sha})`);
    git('push', '-q', 'origin', 'HEAD:main');
    console.log('Publicado en GitHub (raw puede tardar hasta ~5 min en reflejarlo; por Wi-Fi es inmediato).');
  }
  return esc;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const arg = (n, d) => { const k = process.argv.indexOf('--' + n); return k > 0 ? process.argv[k + 1] : d; };
  publicar({id: arg('id'), nombre: arg('nombre', arg('id')), descripcion: arg('descripcion', ''),
    glb: arg('glb'), elementos: arg('elementos'), push: process.argv.includes('--push')});
}
