// Genera public/catalogo.json con los IDs conocidos (ver PLAN_EJECUCION.md §2.3). Después usar sincronizar_catalogo.mjs.
import fs from 'node:fs';
const f = (drive, nombre, bytes) => ({drive, nombre, ...(bytes ? {bytes} : {})});
const cat = {
  version: 1, carpeta_drive: '1MMHybb61ep2gstNUdTF552_t81VwB8kw',
  escenas: [
    {id: 'hito', nombre: 'Hito M33-1 — área seca', descripcion: 'Correas, alimentadores, domo, harneros, puente grúa',
     modelos: [
       {id: 'movil', nombre: 'Ligero (5 M tri.)', archivo: f('1KBg3nLHi5xpA3L2uE5UEXk3NtSLPcpA1', 'hito_web_5M.glb', 17991852)},
       {id: 'alta', nombre: 'Alta (12 M tri.)', pesado: true, archivo: f('17vMz70kZwvMVObYbdLW-ynaKwOaoqv9v', 'hito_web.glb', 31662072)}],
     escena: f('1ElaFhmVtcIIFkgSD-7I879SnpJr2T3_V', 'hito_escena_video.json', 45412),
     recorridos: [
       {nombre: 'Recorrido 25 s', archivo: f('1yawuCXCdrsZEQ6icm5ELLDn_6TuWt15d', 'hito_recorrido.json', 39468)},
       {nombre: 'Recorrido continuo 66 s', archivo: f('1fu7vwBtxyMoDppvrNYMRTi9BGrLttlsV', 'hito_recorrido_50s.json', 99726)},
       {nombre: 'Recorrido de correas 45 s', archivo: f('1e04npkGpO9fmT0sp6lzjhIwpibPAjENl', 'hito_recorrido_correas.json', 71202)}],
     correas: f('1vUP540NkQT96PqHMt-eJEU0kF8RMvkMc', 'hito_correas.json', 8991),
     capas_extra: [{nombre: 'Elementos sueltos', archivo: f('14oB2Qoro31XgCZOaPqIpFMJ7Y06B38CF', 'hito_sueltos.glb', 575940)}]},
    {id: 'area1313', nombre: 'Área 1313 — molinos', descripcion: 'Molinos ML-1401/1402, pórtico CN-1406, pescantes CN-1404/1405',
     modelos: [
       {id: 'movil', nombre: 'Ligero (6 M tri.)', archivo: {url: 'https://raw.githubusercontent.com/eduardosebastian587-wq/NavisMobile/main/modelos_movil/area1313_movil.glb', nombre: 'area1313_movil.glb', bytes: 17371648}},
       {id: 'alta', nombre: 'Alta (21 M tri.)', pesado: true, archivo: f('1-dAhbih23mGeuOojZJyj5z5P7bhuPNcx', 'area1313_web_v4.glb', 46950328)}],
     equipos: {json: f('1KoHOZXvBup82z2BqZZkhtQCcaHDvvbMC', 'area1313_web_v4_equipos.json', 6100), bin: f('1nxZ3oALCMQf2TagVZJy1TA67Doe9wkSd', 'area1313_web_v4_equipos.bin', 8246756)},
     animaciones: f('1K7hxq6BrmVH8FnvPbxGKqyFB_FXwb82v', 'animaciones.json', 32497),
     recorridos: [
       {nombre: 'Recorrido 60 s', archivo: f('1ceTpXi-sVQ9cUjB6z7NVf1RNbZKOd25k', 'area1313_recorrido.json', 91638)},
       {nombre: 'Recorrido 90 s', archivo: f('1sAwO_jCNClN-sqgZtMdeGyagXa6wLklv', 'area1313_recorrido_90s.json', 135236)}]}
  ],
  carpetas: [
    {escena: 'hito', id: '1hXOqD2XSBIL5tIVNijl1unl86dgoMZQu'},
    {escena: 'area1313', id: '1i8hrtOqsLmtepYtAn5kAUrhbaDf8LcMk'},
    {escena: 'area1313', id: '1pKUki46-Yvu0kjT0lQZOlgGXxs7pn-dk'}
  ]
};
fs.writeFileSync('public/catalogo.json', JSON.stringify(cat, null, 1) + '\n');
