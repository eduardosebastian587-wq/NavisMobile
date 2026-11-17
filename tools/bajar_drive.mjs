// Uso: node tools/bajar_drive.mjs <ID_CARPETA> <destino>  — baja los archivos (no carpetas) de una carpeta pública de Drive.
import fs from 'node:fs';
const [id, dest] = process.argv.slice(2);
const html = await (await fetch(`https://drive.google.com/embeddedfolderview?id=${id}`)).text();
const ids = [...html.matchAll(/id="entry-([\w-]+)"/g)].map((m) => m[1]);
const nom = [...html.matchAll(/class="flip-entry-title">([^<]+)</g)].map((m) => m[1].trim().replace(/&amp;/g, '&'));
fs.mkdirSync(dest, { recursive: true });
for (let i = 0; i < ids.length; i++) {
  if (/^_respaldos/i.test(nom[i])) continue;
  const r = await fetch(`https://drive.usercontent.google.com/download?id=${ids[i]}&export=download&confirm=t`);
  const t = r.headers.get('content-type') || '';
  if (!r.ok || /text\/html/.test(t) && !/\.(html|bat)$/i.test(nom[i])) { console.log('omitido (carpeta/sin acceso):', nom[i]); continue; }
  fs.writeFileSync(`${dest}/${nom[i]}`, Buffer.from(await r.arrayBuffer())); console.log('ok', nom[i]);
}
