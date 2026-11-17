// NavisMobile: conecta la interfaz (index.html) con el visor, la navegación y los datos de Drive.
import * as THREE from 'three';
import {Visor} from './visor.js';
import {Navegacion} from './navegacion.js';
import {obtener, obtenerJSON, comprobar, estado, borrar, formatoBytes} from './datos.js';
import {montarEquipos, Animador} from './equipos.js';
import {Correas} from './correas.js';
import {Recorrido} from './recorridos.js';

const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const el = (tag, props = {}, ...hijos) => { const e = Object.assign(document.createElement(tag), props); e.append(...hijos); return e; };
const num = (v, d = 2) => v.toFixed(d).replace('.', ',');

const visor = new Visor($('#lienzo'), {conservar: new URLSearchParams(location.search).has('captura')});
const S = {
  catalogo: null, escena: null, modeloId: null, sel: null, aislado: null, medir: false, medidas: [],
  correas: null, animador: null, recorrido: null, recorridosCache: new Map(), corte: {eje: 'x', inv: false, activo: false}
};

// ------------------------------------------------------------------ navegación
const nav = new Navegacion(visor.camera, $('#lienzo'), {
  alCambiar: () => visor.pedir(),
  puntoEn: (x, y) => visor.puntoEn(x, y),
  alTocar: (x, y, enRecorrido) => {
    if (enRecorrido) { S.recorrido?.pausar(); actualizarRecorridoUI(); return; }
    if (S.medir) return medirToque(x, y);
    seleccionar(visor.mallaEn(x, y));
  },
  alInteractuar: a => { visor.interactuar(a); pivoteVisible(a); },
  alModo: m => marcarModo(m)
});
visor.ticks.push(dt => { const c = nav.actualizar(dt); return c; });
visor.ticks.push(dt => S.recorrido?.tick(dt) || false);
visor.ticks.push(dt => S.animador?.tick(dt) || false);
visor.ticks.push(dt => S.correas?.tick(dt) || false);
visor.ticks.push(() => { actualizarMarca(); actualizarEtiqueta(); return false; });

// marca de pivote
const marca = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({color: 0xffd24a, depthTest: false, transparent: true, opacity: 0.85}));
marca.layers.set(1); marca.renderOrder = 10; marca.visible = false; visor.ayudas.add(marca);
let marcaHasta = 0;
function pivoteVisible(a) { if (a && nav.modo !== 'caminar') marcaHasta = Infinity; else if (!a) marcaHasta = performance.now() + 700; visor.pedir(); }
function actualizarMarca() {
  const v = performance.now() < marcaHasta && nav.modo !== 'caminar';
  if (marca.visible !== v) { marca.visible = v; visor.pedir(); }
  if (v) { marca.position.copy(nav.mira); marca.scale.setScalar(Math.max(0.02, nav.distancia() * 0.012)); visor.pedir(); }
}
function actualizarInfo() {
  $('#info').textContent = `${(visor.triangulos / 1e6).toFixed(2).replace('.', ',')} M tri · ${visor.fps} fps · pivote a ${num(nav.distancia(), 1)} m`;
}
setInterval(actualizarInfo, 500);

// ------------------------------------------------------------------ pestañas y menús
$$('.tabs button').forEach(b => b.onclick = () => {
  $$('.tabs button').forEach(x => x.classList.toggle('on', x === b));
  $$('.pane').forEach(p => p.classList.toggle('on', p.id === b.dataset.p));
});
const irA = p => $(`.tabs button[data-p=${p}]`).click();
$('#bUi').onclick = () => $('#app').classList.toggle('clean');

// ------------------------------------------------------------------ carga con progreso
function cargando(txt, f = null) { $('#carga').hidden = false; $('#cargaTxt').textContent = txt; $('#cargaBar i').style.width = f == null ? '30%' : Math.round(f * 100) + '%'; }
function listo() { $('#carga').hidden = true; }
function error(e) { console.error(e); $('#carga').hidden = false; $('#cargaTxt').textContent = '⚠ ' + (e.message || e); $('#cargaBar i').style.width = '0'; setTimeout(() => ($('#carga').hidden = true), 6000); }
const prog = nombre => (n, t) => cargando(`${nombre}: ${formatoBytes(n)}${t ? ' / ' + formatoBytes(t) : ''}`, t ? n / t : null);

// ------------------------------------------------------------------ escenas
async function iniciarCatalogo() {
  try { S.catalogo = await (await fetch('./catalogo.json')).json(); } catch (e) { return error(e); }
  pintarEscenas();
}
function pintarEscenas() {
  const p = $('#escenas'); p.replaceChildren();
  p.append(el('div', {className: 'nota', textContent: 'Los modelos se descargan desde Google Drive la primera vez y quedan guardados en el teléfono.'}));
  for (const esc of S.catalogo.escenas) {
    const t = el('div', {className: 'tarjeta'}, el('h3', {textContent: esc.nombre}), el('p', {textContent: esc.descripcion || ''}));
    for (const m of esc.modelos) {
      const fila = el('div', {className: 'ops'});
      const est = el('div', {className: 'estado', textContent: '…'});
      const abrir = el('button', {textContent: `Abrir · ${m.nombre}`, onclick: () => abrir_(esc, m)});
      const act = el('button', {textContent: 'Actualizar', onclick: async () => { await abrir_(esc, m, true); pintarEscenas(); }});
      const bor = el('button', {textContent: 'Borrar descarga', onclick: async () => { await borrar(m.archivo); pintarEscenas(); }});
      fila.append(abrir, act, bor);
      t.append(fila, est);
      if (m.pesado) t.append(el('div', {className: 'nota', textContent: '⚠ Calidad alta: consume mucha memoria; puede fallar en teléfonos modestos.'}));
      estado(m.archivo).then(async s => {
        est.textContent = s.descargado ? `Descargado (${formatoBytes(s.bytes)})` : `No descargado (${formatoBytes(m.archivo.bytes || 0)})`;
        est.className = 'estado' + (s.descargado ? ' ok' : '');
        if (s.descargado) { const c = await comprobar(m.archivo); if (c === 'cambio') { est.textContent += ' · hay una versión nueva en Drive'; est.className = 'estado av'; } else if (c === 'sin_conexion') est.textContent += ' · sin conexión'; }
      });
    }
    p.append(t);
  }
  const loc = el('div', {className: 'tarjeta'}, el('h3', {textContent: 'Archivo del teléfono'}), el('p', {textContent: 'Abra un .glb guardado en el dispositivo.'}));
  const inp = el('input', {type: 'file', accept: '.glb,.gltf,model/gltf-binary', hidden: true});
  inp.onchange = async () => { const f = inp.files[0]; if (!f) return; try { cargando('Leyendo ' + f.name); await abrirBuffer(await f.arrayBuffer(), {id: 'local', nombre: f.name}); listo(); } catch (e) { error(e); } };
  loc.append(el('button', {textContent: 'Abrir GLB del teléfono', onclick: () => inp.click()}), inp);
  p.append(loc);
}

let abriendo = false;
async function abrir_(esc, modelo, forzar = false) {
  if (abriendo) return; abriendo = true;
  try {
    detenerTodo();
    cargando('Preparando…');
    const buf = await obtener(modelo.archivo, {forzar, progreso: prog(modelo.archivo.nombre)});
    let escJson = null;
    if (esc.escena) { try { escJson = await obtenerJSON(esc.escena, {forzar}); } catch (e) { console.warn('escena', e); } }
    await abrirBuffer(buf, esc, escJson);
    S.modeloId = modelo.id;
    // extras
    for (const c of esc.capas_extra || []) { try { cargando('Capa: ' + c.nombre); await visor.añadirCapa(c.nombre, await obtener(c.archivo, {forzar}), false); } catch (e) { console.warn(c.nombre, e); } }
    if (esc.correas) { try { S.correas = new Correas(await obtenerJSON(esc.correas, {forzar}), visor.ayudas); } catch (e) { console.warn('correas', e); } }
    if (esc.equipos) {
      try {
        cargando('Equipos…');
        const ej = await obtenerJSON(esc.equipos.json, {forzar}), eb = await obtener(esc.equipos.bin, {forzar, progreso: prog('Equipos')});
        const m = montarEquipos(ej, eb); visor.añadirEquipos(m.grupo, m.mallas);
        let anims = []; if (esc.animaciones) anims = (await obtenerJSON(esc.animaciones, {forzar})).animaciones || [];
        S.animador = new Animador(m.nodos, anims, () => visor.pedir());
        S.animador.alFin = () => pintarAnim();
        visor.calcularCaja(); nav.fijarModelo(visor.caja);
      } catch (e) { console.warn('equipos', e); }
    }
    pintarCapas(); pintarVistas(); pintarAnim(); pintarEscenas();
    listo(); irA('capas');
    if (matchMedia('(max-width:700px)').matches === false) nav.vista('iso');
  } catch (e) { error(e); } finally { abriendo = false; }
}
async function abrirBuffer(buf, esc, escJson) {
  S.escena = esc; S.sel = null; S.aislado = null; S.medidas = []; limpiarMedidas();
  S.correas?.liberar(); S.correas = null; S.animador = null;
  cargando('Procesando modelo…'); await new Promise(r => setTimeout(r, 30));
  const r = await visor.ponerModelo(buf);
  visor.configurarEscena(escJson);
  nav.fijarModelo(visor.caja); nav.fijarModo('orbitar'); marcarModo('orbitar');
  nav.encuadrar(visor.caja, new THREE.Vector3(1, 0.8, 1), false); nav.historial.length = 0;
  prepararCorte(); pintarCapas(); pintarVistas(); pintarProps(null); pintarAnim();
  return r;
}
function detenerTodo() { S.recorrido?.detener(); S.recorrido = null; S.recorridosCache.clear(); if (S.animador) S.animador.reproduciendo = false; }

// ------------------------------------------------------------------ capas, selección, propiedades
function todasLasCapas() { return visor.mallas; }
function aplicarVisibilidad() {
  for (const m of visor.mallas) m.visible = !m.userData.oculta && (!S.aislado || S.aislado.has(m));
  visor.pedir(); pintarCapas();
}
function pintarCapas() {
  const p = $('#capas'); p.replaceChildren();
  if (!visor.mallas.length) { p.textContent = 'Abra una escena desde la pestaña Escenas.'; return; }
  for (const [nombre, g] of visor.capasExtra) {
    const cb = el('input', {type: 'checkbox', checked: g.visible, onchange: () => { g.visible = cb.checked; visor.pedir(); }});
    p.append(el('div', {className: 'item'}, cb, el('div', {className: 'gr'}, nombre, el('small', {textContent: 'capa opcional'}))));
  }
  for (const m of visor.mallas) {
    if (m.userData.capa) continue;
    const cb = el('input', {type: 'checkbox', checked: m.visible, onclick: ev => ev.stopPropagation(), onchange: () => { m.userData.oculta = !cb.checked; aplicarVisibilidad(); }});
    const sw = el('span', {className: 'sw'}); sw.style.background = '#' + (m.userData.color || new THREE.Color(0x888888)).getHexString();
    const it = el('div', {className: 'item' + (S.sel === m ? ' sel' : ''), onclick: () => seleccionar(m)}, cb, sw,
      el('div', {className: 'gr'}, m.name || 'malla', el('small', {textContent: `${m.userData.tri.toLocaleString('es')} triángulos`})));
    p.append(it);
  }
}
function resaltar(m, on) {
  const mt = m?.material; if (!mt?.emissive) return;
  if (on) { m.userData.emi = mt.emissive.getHex(); mt.emissive.setHex(0x1f5fa8); } else if (m.userData.emi !== undefined) mt.emissive.setHex(m.userData.emi);
}
function seleccionar(m) {
  if (S.sel) resaltar(S.sel, false);
  S.sel = m; if (m) resaltar(m, true);
  visor.pedir(); pintarProps(m); pintarCapas();
}
function cajaDe(m) { if (!m.geometry.boundingBox) m.geometry.computeBoundingBox(); return m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld); }
function pintarProps(m) {
  const p = $('#props'); p.replaceChildren();
  if (!m) { p.textContent = 'Toque un objeto para ver sus propiedades.'; return; }
  const c = cajaDe(m), d = c.getSize(new THREE.Vector3()), mt = m.material || {};
  const filas = [['Nombre', m.name], ['Material', mt.name || '—'], ['Triángulos', m.userData.tri.toLocaleString('es')],
    ['Dimensiones', `${num(d.x)} × ${num(d.y)} × ${num(d.z)} m`], ['Color', mt.color ? '#' + (m.userData.color || mt.color).getHexString() : '—'],
    ['Metal / rugosidad', mt.metalness !== undefined ? `${num(mt.metalness)} / ${num(mt.roughness)}` : '—']];
  if (m.userData.equipo) filas.splice(1, 0, ['Equipo', m.userData.equipo]);
  for (const [k, v] of filas) p.append(el('div', {className: 'row'}, el('b', {textContent: k}), el('span', {textContent: v})));
}

$('#bIso').onclick = () => {
  if (S.aislado) { S.aislado = null; $('#bIso').classList.remove('on'); }
  else if (S.sel) { S.aislado = new Set([S.sel]); $('#bIso').classList.add('on'); }
  aplicarVisibilidad();
};
$('#bHide').onclick = () => { if (S.sel) { S.sel.userData.oculta = true; seleccionar(null); aplicarVisibilidad(); } };
$('#bShow').onclick = () => { S.aislado = null; $('#bIso').classList.remove('on'); for (const m of visor.mallas) m.userData.oculta = false; aplicarVisibilidad(); };
$('#bFit').onclick = () => { nav.recordar(); nav.encuadrar(S.sel ? cajaDe(S.sel) : visor.caja); };
$('#bUndo').onclick = () => nav.deshacer();

// ------------------------------------------------------------------ corte
const EJES = {x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 1, 0), z: new THREE.Vector3(0, 0, 1)};
function prepararCorte() { S.corte.activo = false; $('#bClip').classList.remove('on'); $('#clip').hidden = true; visor.fijarCorte(null); }
function actualizarCorte() {
  const {eje, inv} = S.corte, c = visor.caja, k = eje, lo = c.min[k], hi = c.max[k];
  const pos = lo + (hi - lo) * (+$('#clipPos').value / 1000);
  visor.plano.normal.copy(EJES[eje]).multiplyScalar(inv ? -1 : 1);
  visor.plano.constant = inv ? pos : -pos;
  $('#clipVal').textContent = `${eje.toUpperCase()} = ${num(pos, 1)} m`;
  $$('#clip [data-a]').forEach(b => b.classList.toggle('on', b.dataset.a === eje));
  visor.fijarCorte(S.corte.activo ? visor.plano : null);
}
$('#bClip').onclick = () => { S.corte.activo = !S.corte.activo; $('#bClip').classList.toggle('on', S.corte.activo); $('#clip').hidden = !S.corte.activo; actualizarCorte(); };
$$('#clip [data-a]').forEach(b => b.onclick = () => { S.corte.eje = b.dataset.a; actualizarCorte(); });
$('#clipPos').oninput = actualizarCorte;
$('#clipFlip').onclick = () => { S.corte.inv = !S.corte.inv; actualizarCorte(); };

// ------------------------------------------------------------------ medir
const medMat = new THREE.LineBasicMaterial({color: 0xffd24a, depthTest: false}); const medGrupo = new THREE.Group(); medGrupo.layers.set(1); visor.ayudas.add(medGrupo);
function limpiarMedidas() { S.medidas = []; medGrupo.clear(); $('#mlabel').hidden = true; S.medA = null; S.medB = null; }
$('#bMeas').onclick = () => { S.medir = !S.medir; $('#bMeas').classList.toggle('on', S.medir); if (!S.medir) limpiarMedidas(); visor.pedir(); };
function medirToque(x, y) {
  const q = visor.puntoEn(x, y); if (!q) return;
  if (S.medA && S.medB) limpiarMedidas();
  if (!S.medA) { S.medA = q; const s = new THREE.Mesh(new THREE.SphereGeometry(1, 8, 6), marca.material); s.position.copy(q); s.userData.medida = true; s.layers.set(1); medGrupo.add(s); }
  else {
    S.medB = q;
    const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints([S.medA, q]), medMat); l.layers.set(1); l.renderOrder = 11; medGrupo.add(l);
    const s = new THREE.Mesh(new THREE.SphereGeometry(1, 8, 6), marca.material); s.position.copy(q); s.layers.set(1); medGrupo.add(s);
  }
  visor.pedir();
}
function actualizarEtiqueta() {
  const l = $('#mlabel');
  for (const s of medGrupo.children) if (s.isMesh) s.scale.setScalar(Math.max(0.02, s.position.distanceTo(visor.camera.position) * 0.006));
  if (!S.medA || !S.medB) { if (!l.hidden) l.hidden = true; return; }
  const mid = S.medA.clone().add(S.medB).multiplyScalar(0.5), d = S.medA.distanceTo(S.medB);
  const p = mid.clone().project(visor.camera);
  if (p.z > 1 || Math.abs(p.x) > 1.2 || Math.abs(p.y) > 1.2) { l.hidden = true; return; }
  l.hidden = false; l.textContent = `${num(d)} m`;
  const cv = $('#lienzo'); l.style.left = ((p.x + 1) / 2 * cv.clientWidth) + 'px'; l.style.top = ((1 - p.y) / 2 * cv.clientHeight) + 'px';
}

// ------------------------------------------------------------------ panel de navegación
function marcarModo(m) {
  $$('#modos [data-m]').forEach(b => b.classList.toggle('on', b.dataset.m === m));
  $('#palanca').hidden = $('#vert').hidden = m !== 'caminar';
  $('#filaVel').style.display = m === 'caminar' ? '' : 'none';
}
$$('#modos [data-m]').forEach(b => b.onclick = () => { nav.fijarModo(b.dataset.m); marcarModo(b.dataset.m); });
$('#bFino').onclick = () => { $('#fino').hidden = !$('#fino').hidden; $('#bFino').classList.toggle('on', !$('#fino').hidden); };
$('#sens').oninput = e => { nav.sens = +e.target.value; $('#sensVal').textContent = num(nav.sens) + '×'; };
$('#vel').oninput = e => { nav.velocidad = +e.target.value; $('#velVal').textContent = num(nav.velocidad, 1) + ' m/s'; };
$('#fov').oninput = e => { nav.camera.fov = +e.target.value; nav.camera.updateProjectionMatrix(); $('#fovVal').textContent = nav.camera.fov + '°'; visor.pedir(); };
$$('#fino [data-g]').forEach(b => b.onclick = () => {
  nav.recordar();
  const p = THREE.MathUtils.degToRad(+$('#pasoG').value), c = nav.modo === 'caminar', s = c ? 1 : -1;
  ({izq: () => nav.girar(-s * p, 0), der: () => nav.girar(s * p, 0), arr: () => nav.girar(0, c ? p : -p), aba: () => nav.girar(0, c ? -p : p)})[b.dataset.g]();
});
$$('#fino [data-d]').forEach(b => b.onclick = () => {
  nav.recordar(); const p = +$('#pasoM').value;
  const D = {ade: [0, 0, p], atr: [0, 0, -p], izq: [-p, 0, 0], der: [p, 0, 0], sub: [0, p, 0], baj: [0, -p, 0]}[b.dataset.d];
  if (D) nav.mover(...D);
});
// palanca
{
  const pal = $('#palanca'), per = $('#perilla'), R = 45; let id = null;
  const mover = e => { const r = pal.getBoundingClientRect(); let dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2); const l = Math.hypot(dx, dy); if (l > R) { dx *= R / l; dy *= R / l; } per.style.transform = `translate(${dx}px,${dy}px)`; nav.palanca.set(dx / R, dy / R); };
  pal.addEventListener('pointerdown', e => { id = e.pointerId; pal.setPointerCapture(id); mover(e); nav.recordar(); visor.interactuar(true); });
  pal.addEventListener('pointermove', e => { if (e.pointerId === id) mover(e); });
  const fin = e => { if (e.pointerId !== id) return; id = null; per.style.transform = ''; nav.palanca.set(0, 0); visor.interactuar(false); };
  pal.addEventListener('pointerup', fin); pal.addEventListener('pointercancel', fin);
  $$('#vert [data-v]').forEach(b => { b.addEventListener('pointerdown', e => { b.setPointerCapture(e.pointerId); nav.vertical = +b.dataset.v; }); const f = () => (nav.vertical = 0); b.addEventListener('pointerup', f); b.addEventListener('pointercancel', f); });
}

// ------------------------------------------------------------------ vistas
const claveVistas = () => 'navismobile:vistas:' + (S.escena?.id || 'x');
const leerVistas = () => { try { return JSON.parse(localStorage.getItem(claveVistas())) || []; } catch { return []; } };
function pintarVistas() {
  const p = $('#vistas'); p.replaceChildren();
  const fila = el('div', {className: 'ops', style: 'display:flex;flex-wrap:wrap;gap:6px'});
  for (const [k, n] of [['planta', 'Planta'], ['frente', 'Frente'], ['atras', 'Atrás'], ['izquierda', 'Izquierda'], ['derecha', 'Derecha'], ['iso', 'Iso']])
    fila.append(el('button', {textContent: n, onclick: () => nav.vista(k)}));
  p.append(fila, el('div', {className: 'cat', textContent: 'Vistas guardadas'}));
  p.append(el('button', {textContent: 'Guardar vista actual', onclick: () => {
    const nombre = prompt('Nombre de la vista:', 'Vista ' + (leerVistas().length + 1)); if (!nombre) return;
    const v = leerVistas(); v.push({nombre, e: nav.estado()}); localStorage.setItem(claveVistas(), JSON.stringify(v)); pintarVistas();
  }}));
  leerVistas().forEach((v, i) => p.append(el('div', {className: 'item', onclick: () => { nav.recordar(); nav.aplicar(v.e, true); }},
    el('div', {className: 'gr', textContent: v.nombre}),
    el('button', {textContent: '✕', onclick: ev => { ev.stopPropagation(); const a = leerVistas(); a.splice(i, 1); localStorage.setItem(claveVistas(), JSON.stringify(a)); pintarVistas(); }}))));
}

// ------------------------------------------------------------------ animación
const mmss = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
function actualizarRecorridoUI() { const b = $('#recPlay'); if (b) b.textContent = S.recorrido?.reproduciendo ? '⏸' : '▶'; }
function pintarAnim() {
  const p = $('#anim'); p.replaceChildren();
  const esc = S.escena;
  if (!esc || !esc.recorridos) { p.textContent = visor.mallas.length ? 'Esta escena no tiene recorridos ni animaciones.' : 'Abra una escena desde la pestaña Escenas.'; return; }
  p.append(el('div', {className: 'cat', textContent: 'Recorridos de cámara'}));
  const sel = el('select', {id: 'recSel'}, el('option', {value: '', textContent: '— elegir —'}), ...esc.recorridos.map((r, i) => el('option', {value: i, textContent: r.nombre})));
  const play = el('button', {id: 'recPlay', textContent: '▶', onclick: async () => {
    if (!S.recorrido) { if (sel.value === '') return; await cargarRecorrido(+sel.value); }
    if (!S.recorrido) return;
    if (S.recorrido.reproduciendo) S.recorrido.pausar(); else { S.recorrido.reproducir(); visor.pedir(); }
    actualizarRecorridoUI();
  }});
  const barra = el('input', {id: 'recBarra', type: 'range', min: 0, max: 1000, value: 0, oninput: () => { if (!S.recorrido) return; S.recorrido.poner(barra.value / 1000 * S.recorrido.duracion); visor.pedir(); }});
  const tiempo = el('span', {id: 'recT', textContent: '0:00'});
  sel.onchange = async () => { S.recorrido?.detener(); S.recorrido = null; if (sel.value !== '') await cargarRecorrido(+sel.value); actualizarRecorridoUI(); };
  const vel = el('select', {onchange: () => { if (S.recorrido) S.recorrido.velocidad = +vel.value; S.velRec = +vel.value; }}, ...[0.25, 0.5, 1, 1.5, 2].map(v => el('option', {value: v, textContent: v + '×', selected: v === 1})));
  p.append(el('div', {className: 'ctl'}, sel), el('div', {className: 'ctl'}, play, barra, tiempo), el('div', {className: 'ctl'}, el('span', {textContent: 'Velocidad'}), vel));
  if (esc.id === 'hito' || S.correas) {
    const cb = el('input', {type: 'checkbox', checked: S.correas?.activa || false, onchange: () => { S.correas?.mostrar(cb.checked); visor.pedir(); }});
    p.append(el('label', {className: 'ctl'}, cb, 'Correas en movimiento'));
  }
  if (S.animador) {
    p.append(el('div', {className: 'cat', textContent: 'Animaciones de equipos'}));
    const an = S.animador; if (!an.lista.length) p.append(el('div', {className: 'nota', textContent: 'Sin animaciones.'}));
    for (const a of an.lista) {
      const activa = an.actual === a, nValidas = an.pistasValidas(a).length;
      p.append(el('div', {className: 'item' + (activa ? ' sel' : ''), onclick: () => { an.reproduciendo = false; an.elegir(a.id); pintarAnim(); }},
        el('div', {className: 'gr'}, a.nombre, el('small', {textContent: `${a.duracion} s · ${nValidas}/${a.pistas.length} pistas aplicables${a.bucle === 'bucle' ? ' · bucle' : ''}`}))));
    }
    if (an.actual) {
      const ign = an.ignoradas(); 
      const pl = el('button', {textContent: an.reproduciendo ? '⏸' : '▶', onclick: () => { if (!an.reproduciendo && an.t >= an.duracion() && an.actual.bucle !== 'bucle') an.t = 0; an.reproduciendo = !an.reproduciendo; pl.textContent = an.reproduciendo ? '⏸' : '▶'; visor.pedir(); }});
      const bb = el('input', {type: 'range', min: 0, max: 1000, value: 0, oninput: () => { an.reproduciendo = false; pl.textContent = '▶'; an.t = bb.value / 1000 * an.duracion(); an.aplicar(an.t); }});
      const v2 = el('select', {onchange: () => (an.velocidad = +v2.value)}, ...[0.25, 0.5, 1, 2, 4].map(v => el('option', {value: v, textContent: v + '×', selected: v === an.velocidad})));
      p.append(el('div', {className: 'ctl'}, pl, bb, v2));
      an.alFrame = () => { bb.value = Math.round((an.t % (an.duracion() || 1)) / (an.duracion() || 1) * 1000); };
      if (ign.length) p.append(el('div', {className: 'nota', textContent: `Pistas no aplicables en este modelo (cámara, disciplinas, visibilidad): ${[...new Set(ign.map(x => x.split('.')[0]))].join(', ')}.`}));
    }
  }
}
async function cargarRecorrido(i) {
  const r = S.escena.recorridos[i]; cargando('Recorrido: ' + r.nombre);
  try {
    const datos = await obtenerJSON(r.archivo, {progreso: prog(r.archivo.nombre)});
    S.recorrido = new Recorrido(datos, nav, {
      alCuadro: t => {
        if (S.animador) { if (!S.animador.actual) { const c = S.animador.lista.find(a => a.id === 'ciclo-completo') || S.animador.lista[0]; if (c) S.animador.actual = c; } S.animador.aplicar(Math.max(0, t)); }
        const bar = $('#recBarra'); if (bar) bar.value = Math.round(S.recorrido.t / S.recorrido.duracion * 1000);
        const tt = $('#recT'); if (tt) tt.textContent = `${mmss(S.recorrido.t)} / ${mmss(S.recorrido.duracion)}`;
      },
      alFin: actualizarRecorridoUI
    });
    S.recorrido.velocidad = S.velRec || 1; listo();
  } catch (e) { error(e); }
}

// ------------------------------------------------------------------ arranque
window.nm = {visor, nav, S, abrir: (e, m) => abrir_(S.catalogo.escenas.find(x => x.id === e), S.catalogo.escenas.find(x => x.id === e).modelos.find(x => x.id === m)), seleccionar, cargarRecorrido};
marcarModo('orbitar');
iniciarCatalogo();
