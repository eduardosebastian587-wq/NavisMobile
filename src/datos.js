// Acceso a los archivos: descarga desde Drive (o URL), caché en el teléfono (Cache API) y detección de cambios.
const CACHE = 'navismobile-v1';
const META = 'navismobile-meta:';
const DEV = import.meta.env.DEV;

export const urlDe = a => a.url || `https://drive.usercontent.google.com/download?id=${a.drive}&export=download&confirm=t`;
const clave = a => `https://cache.local/${a.drive || encodeURIComponent(a.url)}`;
const leerMeta = a => { try { return JSON.parse(localStorage.getItem(META + (a.drive || a.url))) || null; } catch { return null; } };
const guardarMeta = (a, m) => localStorage.setItem(META + (a.drive || a.url), JSON.stringify(m));

try { navigator.storage?.persist?.(); } catch {}

async function cache() { return 'caches' in self ? caches.open(CACHE) : null; }

/** Estado de un archivo en el teléfono: {descargado, bytes, fecha} */
export async function estado(a) {
  const m = leerMeta(a), c = await cache();
  const ok = c && m && await c.match(clave(a));
  return {descargado: !!ok, bytes: ok ? m.bytes : 0, fecha: m?.descargado || null};
}

/** Compara con Drive (HEAD). → 'al_dia' | 'cambio' | 'sin_conexion' | 'no_descargado' */
export async function comprobar(a) {
  const m = leerMeta(a), c = await cache();
  if (!m || !c || !(await c.match(clave(a)))) return 'no_descargado';
  try {
    const r = await fetch(urlDe(a), {method: 'HEAD'});
    if (!r.ok) return 'sin_conexion';
    const len = +r.headers.get('content-length') || 0, mod = r.headers.get('last-modified') || '';
    if ((len && m.bytes && len !== m.bytes) || (mod && m.modificado && mod !== m.modificado)) return 'cambio';
    return 'al_dia';
  } catch { return 'sin_conexion'; }
}

async function descargar(a, progreso) {
  const r = await fetch(urlDe(a));
  if (!r.ok) throw new Error(`HTTP ${r.status} al descargar ${a.nombre}`);
  const total = +r.headers.get('content-length') || a.bytes || 0;
  const trozos = []; let n = 0;
  if (r.body?.getReader) {
    const rd = r.body.getReader();
    for (;;) { const {done, value} = await rd.read(); if (done) break; trozos.push(value); n += value.length; progreso?.(n, total); }
  } else { const b = new Uint8Array(await r.arrayBuffer()); trozos.push(b); n = b.length; progreso?.(n, n); }
  const buf = new Uint8Array(n); let o = 0; for (const t of trozos) { buf.set(t, o); o += t.length; }
  return {buf: buf.buffer, modificado: r.headers.get('last-modified') || ''};
}

/** Devuelve el ArrayBuffer del archivo (caché o descarga). forzar=true vuelve a descargar. */
export async function obtener(a, {progreso, forzar = false} = {}) {
  if (DEV && a.nombre) {                       // desarrollo: carpeta local servida por Vite
    try {
      const r = await fetch(`/datos/${a.nombre}`);
      if (r.ok && !(r.headers.get('content-type') || '').includes('html')) {
        const b = await r.arrayBuffer(); progreso?.(b.byteLength, b.byteLength); return b;
      }
    } catch {}
  }
  const c = await cache();
  if (!forzar && c) { const h = await c.match(clave(a)); if (h) { const b = await h.arrayBuffer(); progreso?.(b.byteLength, b.byteLength); return b; } }
  const {buf, modificado} = await descargar(a, progreso);
  if (c) {
    try {
      await c.put(clave(a), new Response(buf.slice(0)));
      guardarMeta(a, {bytes: buf.byteLength, modificado, descargado: Date.now()});
    } catch (e) { console.warn('No se pudo guardar en caché:', e); }
  }
  return buf;
}

export async function obtenerJSON(a, o) { return JSON.parse(new TextDecoder().decode(await obtener(a, o))); }

export async function borrar(a) {
  const c = await cache(); if (c) await c.delete(clave(a));
  localStorage.removeItem(META + (a.drive || a.url));
}

export const formatoBytes = n => n >= 1e9 ? (n / 1e9).toFixed(2) + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1e3)) + ' kB';
