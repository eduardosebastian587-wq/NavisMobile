// Acceso a archivos del catálogo: locales (empaquetados), URL directa o Google Drive, con caché en el teléfono.
const CACHE = 'navismobile-v1';
const META = 'navismobile-meta';

const meta = () => { try { return JSON.parse(localStorage.getItem(META) || '{}'); } catch { return {}; } };
const guardarMeta = m => { try { localStorage.setItem(META, JSON.stringify(m)); } catch { /* sin espacio */ } };
// clave estable: la ruta relativa no depende de si el catálogo vino del PC (Wi-Fi) o de GitHub
const clave = a => a.drive || a.url || a.ruta;
const v = a => a.sha ? (a.url?.includes('?') ? '&' : '?') + 'v=' + a.sha : '';

/** URL de descarga de un archivo del catálogo ({ruta} | {url} | {drive}). Una {ruta} de un catálogo
 *  remoto se resuelve contra la URL del catálogo (_base); sin _base, es un archivo incluido en la app. */
export function urlDe(a) {
  if (a.ruta) return a._base ? new URL(a.ruta, a._base).href + v(a) : import.meta.env.BASE_URL + a.ruta;
  if (a.url) return a.url + v(a);
  return `https://drive.usercontent.google.com/download?id=${a.drive}&export=download&confirm=t`;
}
export const esLocal = a => !!a.ruta && !a._base;
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
    // con huella (sha) en el catálogo, la copia guardada solo sirve si es de esa misma versión
    if (hit && (!a.sha || meta()[clave(a)]?.sha === a.sha)) return hit.arrayBuffer();
  }
  const {buf, r} = await descargar(a, progreso);
  try {
    await cache.put(k, new Response(buf));
    const m = meta(); m[clave(a)] = {mod: r.headers.get('last-modified') || '', bytes: buf.byteLength, sha: a.sha || '', t: Date.now()}; guardarMeta(m);
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
  if (a.sha) return m.sha === a.sha ? 'al_dia' : 'cambio';     // sin consultar la red
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
// ------------------------------------------------------------------ catálogo remoto
// Orden: PC por Wi-Fi (si se configuró) -> GitHub -> última copia guardada -> copia incluida en la app.
// Así se agregan o actualizan áreas publicando archivos, sin recompilar ni reinstalar la APK.
export const GITHUB = 'https://raw.githubusercontent.com/eduardosebastian587-wq/NavisMobile/main/areas/catalogo.json';
const CAT = 'navismobile-catalogo', LAN = 'navismobile-pc';
export const urlPc = () => { try { return localStorage.getItem(LAN) || ''; } catch { return ''; } };
export function fijarPc(u) {
  u = (u || '').trim();
  if (u && !/^https?:\/\//.test(u)) u = 'http://' + u;
  if (u && !/\.json$/.test(u)) u = u.replace(/\/?$/, '/catalogo.json');
  try { u ? localStorage.setItem(LAN, u) : localStorage.removeItem(LAN); } catch { /* sin almacenamiento */ }
  return u;
}
function marcar(c, base) {
  const rec = o => {
    if (Array.isArray(o)) return o.forEach(rec);
    if (!o || typeof o !== 'object') return;
    if (o.ruta && base) o._base = base;
    Object.values(o).forEach(rec);
  };
  rec(c.escenas); return c;
}
export async function catalogo() {
  for (const [u, origen] of [[urlPc(), 'PC (Wi-Fi)'], [GITHUB, 'GitHub']]) {
    if (!u) continue;
    try {
      const r = await fetch(u + '?t=' + Date.now(), {cache: 'no-store', signal: AbortSignal.timeout(origen === 'GitHub' ? 8000 : 3000)});
      if (!r.ok) continue;
      const c = await r.json();
      try { localStorage.setItem(CAT, JSON.stringify({c, u, origen, t: Date.now()})); } catch { /* sin espacio */ }
      return Object.assign(marcar(c, u), {origen});
    } catch { /* se prueba la siguiente fuente */ }
  }
  try {
    const g = JSON.parse(localStorage.getItem(CAT) || 'null');
    if (g) return Object.assign(marcar(g.c, g.u), {origen: `copia guardada de ${g.origen} (sin conexión)`});
  } catch { /* copia dañada */ }
  const c = await (await fetch(import.meta.env.BASE_URL + 'catalogo.json')).json();
  return Object.assign(marcar(c, c.base), {origen: 'incluido en la app'});
}
