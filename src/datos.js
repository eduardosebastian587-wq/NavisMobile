// Acceso a archivos del catálogo: locales (empaquetados), URL directa o Google Drive, con caché en el teléfono.
const CACHE = 'navismobile-v1';
const META = 'navismobile-meta';

const meta = () => { try { return JSON.parse(localStorage.getItem(META) || '{}'); } catch { return {}; } };
const guardarMeta = m => { try { localStorage.setItem(META, JSON.stringify(m)); } catch { /* sin espacio */ } };
const clave = a => a.drive || a.url || a.ruta;

/** URL de descarga de un archivo del catálogo ({ruta} | {url} | {drive}). */
export function urlDe(a) {
  if (a.ruta) return import.meta.env.BASE_URL + a.ruta;
  if (a.url) return a.url;
  return `https://drive.usercontent.google.com/download?id=${a.drive}&export=download&confirm=t`;
}
const esLocal = a => !!a.ruta;
const claveCache = a => `https://cache.local/${encodeURIComponent(clave(a))}`;

async function descargar(a, progreso) {
  const r = await fetch(urlDe(a));
  if (!r.ok) throw new Error(`HTTP ${r.status} al descargar ${a.nombre || clave(a)}`);
  const total = Number(r.headers.get('content-length')) || a.bytes || 0;
  const lector = r.body?.getReader();
  if (!lector) { const b = await r.arrayBuffer(); progreso?.(b.byteLength, b.byteLength); return {buf: b, r}; }
  const trozos = []; let n = 0;
  for (;;) {
    const {done, value} = await lector.read(); if (done) break;
    trozos.push(value); n += value.length; progreso?.(n, total);
  }
  const out = new Uint8Array(n); let o = 0;
  for (const t of trozos) { out.set(t, o); o += t.length; }
  return {buf: out.buffer, r};
}

/** Devuelve el ArrayBuffer del archivo, usando la caché si ya está descargado. */
export async function obtener(a, {progreso, forzar = false} = {}) {
  if (esLocal(a)) { const {buf} = await descargar(a, progreso); return buf; }
  const cache = await caches.open(CACHE), k = claveCache(a);
  if (!forzar) {
    const hit = await cache.match(k);
    if (hit) return hit.arrayBuffer();
  }
  const {buf, r} = await descargar(a, progreso);
  try {
    await cache.put(k, new Response(buf));
    const m = meta(); m[clave(a)] = {mod: r.headers.get('last-modified') || '', bytes: buf.byteLength, t: Date.now()}; guardarMeta(m);
    navigator.storage?.persist?.();
  } catch { /* la caché puede fallar por espacio: se sigue sin ella */ }
  return buf;
}

/** Texto JSON de un archivo (se cachea igual que el resto). */
export async function obtenerJson(a, o) { return JSON.parse(new TextDecoder().decode(await obtener(a, o))); }

/** 'local' | 'al_dia' | 'cambio' | 'sin_conexion' | 'no_descargado' */
export async function comprobar(a) {
  if (esLocal(a)) return 'local';
  const m = meta()[clave(a)];
  if (!m || !(await (await caches.open(CACHE)).match(claveCache(a)))) return 'no_descargado';
  try {
    const r = await fetch(urlDe(a), {method: 'HEAD'});
    if (!r.ok) return 'sin_conexion';
    const mod = r.headers.get('last-modified') || '', len = Number(r.headers.get('content-length')) || 0;
    return (mod && m.mod && mod !== m.mod) || (len && len !== m.bytes) ? 'cambio' : 'al_dia';
  } catch { return 'sin_conexion'; }
}
export const tamano = a => meta()[clave(a)]?.bytes || 0;
export async function borrar(a) {
  if (esLocal(a)) return;
  await (await caches.open(CACHE)).delete(claveCache(a));
  const m = meta(); delete m[clave(a)]; guardarMeta(m);
}
export async function catalogo() {
  const r = await fetch(import.meta.env.BASE_URL + 'catalogo.json');
  return r.json();
}
