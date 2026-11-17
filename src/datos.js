// Acceso a archivos: Drive (o URL) con caché local (Cache API) y detección de cambios por HEAD.
import { Capacitor, CapacitorHttp } from '@capacitor/core';
import { Filesystem, Directory } from '@capacitor/filesystem';
const nativo = Capacitor.isNativePlatform();
const CACHE = 'navismobile-v1';
const META = 'navismobile-meta';
const dr = (id) => `https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`;
const clave = (a) => `https://cache.local/${a.drive || encodeURIComponent(a.url || a.nombre)}`;
const metas = () => JSON.parse(localStorage.getItem(META) || '{}');
const guardarMeta = (a, m) => { const t = metas(); t[clave(a)] = m; localStorage.setItem(META, JSON.stringify(t)); };

export const urlDe = (a) => a.url || dr(a.drive);

export async function persistir() { try { await navigator.storage?.persist?.(); } catch {} }

async function enDev(a) {
  if (!import.meta.env.DEV) return null;
  try { const r = await fetch(`/datos/${a.nombre}`); if (r.ok && !/html/.test(r.headers.get('content-type') || '')) return await r.arrayBuffer(); } catch {}
  return null;
}

/** Descarga con progreso: progreso(bytesRecibidos, bytesTotales). */
// Android: el WebView envía Sec-Fetch-Mode: cors y Drive responde 403 sin CORS; se descarga por la red nativa.
async function descargarNativo(a, progreso) {
  const ruta = `navis_${Date.now()}.tmp`;
  const h = await Filesystem.addListener('progress', (p) => { if (p.url === urlDe(a)) progreso?.(p.bytes, p.contentLength > 0 ? p.contentLength : a.bytes || 0); });
  try {
    await Filesystem.downloadFile({ url: urlDe(a), path: ruta, directory: Directory.Cache, progress: true });
    const { uri } = await Filesystem.getUri({ path: ruta, directory: Directory.Cache });
    const r = await fetch(Capacitor.convertFileSrc(uri));
    const buf = await r.arrayBuffer();
    if (buf.byteLength < 1024 && /<html/i.test(new TextDecoder().decode(buf.slice(0, 200)))) throw new Error(`Drive no entregó el archivo: ${a.nombre}`);
    let mod = '';
    try { mod = (await cabecerasHead(a))['last-modified'] || ''; } catch {}
    await (await caches.open(CACHE)).put(clave(a), new Response(buf.slice(0), { headers: { 'content-length': String(buf.byteLength) } }));
    guardarMeta(a, { modificado: mod, bytes: buf.byteLength, fecha: Date.now() });
    return buf;
  } finally { h.remove(); try { await Filesystem.deleteFile({ path: ruta, directory: Directory.Cache }); } catch {} }
}
async function cabecerasHead(a) {
  if (nativo) {
    const r = await CapacitorHttp.request({ url: urlDe(a), method: 'HEAD' });
    return Object.fromEntries(Object.entries(r.headers || {}).map(([k, v]) => [k.toLowerCase(), v]));
  }
  const r = await fetch(urlDe(a), { method: 'HEAD' });
  return { 'last-modified': r.headers.get('last-modified') || '', 'content-length': r.headers.get('content-length') || '' };
}
async function descargar(a, progreso) {
  if (nativo) return descargarNativo(a, progreso);
  const r = await fetch(urlDe(a));
  if (!r.ok) throw new Error(`Descarga fallida (${r.status}): ${a.nombre}`);
  const total = Number(r.headers.get('content-length')) || a.bytes || 0;
  const trozos = []; let n = 0;
  const rd = r.body.getReader();
  for (;;) { const { done, value } = await rd.read(); if (done) break; trozos.push(value); n += value.length; progreso?.(n, total); }
  const buf = new Uint8Array(n); let o = 0; for (const t of trozos) { buf.set(t, o); o += t.length; }
  const c = await caches.open(CACHE);
  await c.put(clave(a), new Response(buf.slice(0), { headers: { 'content-length': String(n) } }));
  guardarMeta(a, { modificado: r.headers.get('last-modified') || '', bytes: n, fecha: Date.now() });
  return buf.buffer;
}

/** Devuelve el ArrayBuffer del archivo (caché primero; descarga si hace falta). */
export async function obtener(a, { progreso, forzar = false } = {}) {
  if (!forzar) {
    const d = await enDev(a); if (d) return d;
    const c = await caches.open(CACHE), r = await c.match(clave(a));
    if (r) return await r.arrayBuffer();
  }
  return descargar(a, progreso);
}
export const obtenerJSON = async (a, o) => JSON.parse(new TextDecoder().decode(await obtener(a, o)));

/** 'al_dia' | 'cambio' | 'sin_conexion' | 'no_descargado' */
export async function comprobar(a) {
  const c = await caches.open(CACHE);
  if (!(await c.match(clave(a)))) return 'no_descargado';
  if (a.url && !a.drive) return 'al_dia';
  try {
    const hd = await cabecerasHead(a), m = metas()[clave(a)] || {};
    const mod = hd['last-modified'] || '', len = Number(hd['content-length']) || 0;
    return (mod && m.modificado && mod !== m.modificado) || (len && m.bytes && len !== m.bytes) ? 'cambio' : 'al_dia';
  } catch { return 'sin_conexion'; }
}
export async function borrar(a) {
  await (await caches.open(CACHE)).delete(clave(a));
  const t = metas(); delete t[clave(a)]; localStorage.setItem(META, JSON.stringify(t));
}
export const tamano = (a) => metas()[clave(a)]?.bytes || a.bytes || 0;
export const mb = (b) => (b / 1048576).toFixed(1) + ' MB';
