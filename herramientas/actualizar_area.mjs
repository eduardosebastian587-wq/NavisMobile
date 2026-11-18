// Cadena completa, un solo comando: Navisworks (abierto, con el plugin NwMobileExport) -> .nmraw -> GLB -> catálogo.
// Uso:
//   node herramientas/actualizar_area.mjs --id area1313d --nombre "Área 1313" --raices 0:27/6/0/0
//        [--excluir id1,id2] [--descripcion "..."] [--push] [--trabajo "F:/proyecto animación/NavisMobile/trabajo"]
//        [--celda 0.15 --div 3 --min 0.06 --margen 15] [--ratio 0.25] [--solo-convertir]
// --raices / --excluir: ids de nodos del árbol (los que devuelve la herramienta MCP find_items).
// --solo-convertir: reutiliza el .nmraw ya exportado (para probar otra simplificación sin tocar Navisworks).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {publicar, REPO} from './publicar_area.mjs';

const arg = (n, d) => { const k = process.argv.indexOf('--' + n); return k > 0 ? process.argv[k + 1] : d; };
const id = arg('id'); if (!id) throw new Error('Falta --id');
const T0 = Date.now(), seg = () => ((Date.now() - T0) / 1000).toFixed(0) + ' s';
const log = m => console.log(`[${seg().padStart(5)}] ${m}`);
const TRABAJO = path.join(arg('trabajo', 'F:/proyecto animación/NavisMobile/trabajo'), id);
const PY = arg('python', 'C:/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe');
const H = path.join(REPO, 'herramientas', 'navismobile-export', 'herramientas');
fs.mkdirSync(TRABAJO, {recursive: true});
const raw = path.join(TRABAJO, `${id}.nmraw`), completo = path.join(TRABAJO, `${id}_completo.glb`);
const movil = path.join(TRABAJO, `${id}_movil.glb`), elementos = path.join(TRABAJO, `${id}_elementos.json`);

function correr(cmd, args, env) {
  const r = spawnSync(cmd, args, {stdio: ['ignore', 'pipe', 'inherit'], encoding: 'utf8', env: {...process.env, ...env}});
  const ult = (r.stdout || '').trim().split('\n').slice(-2).join(' | ');
  if (r.status !== 0) throw new Error(`${path.basename(args[0] || cmd)} falló: ${ult}`);
  return ult;
}

async function exportar() {
  const cola = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData/Local'), 'NwMobileExport', 'cola');
  if (!fs.existsSync(cola)) throw new Error('No existe la cola del plugin: ¿está Navisworks abierto con NwMobileExport instalado?');
  const job = `${id}_${Date.now()}`, estado = path.join(cola, `${job}.estado.json`);
  const t = {raices: arg('raices', '').split(',').filter(Boolean), excluir: arg('excluir', '').split(',').filter(Boolean), salida: raw.replace(/\\/g, '/')};
  if (!t.raices.length) throw new Error('Falta --raices');
  fs.writeFileSync(path.join(cola, `${job}.tmp`), JSON.stringify(t));
  fs.renameSync(path.join(cola, `${job}.tmp`), path.join(cola, `${job}.trabajo.json`));
  log('Exportando desde Navisworks…');
  for (let espera = 0; ; espera++) {
    await new Promise(r => setTimeout(r, 3000));
    let e = null; try { e = JSON.parse(fs.readFileSync(estado, 'utf8')); } catch { /* aún no existe */ }
    if (!e) { if (espera > 20) throw new Error('El plugin no tomó el trabajo en 60 s: ¿Navisworks abierto y libre?'); continue; }
    if (e.estado === 'error') throw new Error('Navisworks: ' + e.error);
    if (e.estado === 'cancelado') throw new Error('Exportación cancelada');
    process.stdout.write(`\r[${seg().padStart(5)}]   ${(e.triangulos / 1e6).toFixed(1)} M triángulos, ${e.piezas} piezas, ${e.tags} TAG   `);
    if (e.estado === 'listo') { process.stdout.write('\n'); break; }
  }
}

if (!process.argv.includes('--solo-convertir')) await exportar();
else if (!fs.existsSync(raw)) throw new Error(`No existe ${raw}`);
log('Convirtiendo a GLB…');
log(correr(PY, [path.join(H, 'raw_a_glb.py'), raw, completo, elementos,
  '--celda', arg('celda', '0.15'), '--div', arg('div', '3'), '--min', arg('min', '0.06'), '--margen', arg('margen', '15')]));
log('Optimizando…');
log(correr('node', [path.join(H, 'optimizar.cjs'), completo, movil, '--ratio', arg('ratio', '0.25'),
  '--modulos', path.join(REPO, 'node_modules')], {NODE_OPTIONS: '--max-old-space-size=8000'}));
fs.rmSync(completo, {force: true});            // intermedio de ~100 MB: se regenera en segundos desde el .nmraw
publicar({id, nombre: arg('nombre', id), descripcion: arg('descripcion', ''), glb: movil, elementos, push: process.argv.includes('--push')});
log('LISTO. En la app: Escenas › Recargar.');
