// NavisMobile: conecta la interfaz (index.html) con el visor, la navegación y los datos.
import * as THREE from 'three';
import {Visor} from './visor.js';
import {Navegacion} from './navegacion.js';
import * as datos from './datos.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (tag, props = {}, ...hijos) => {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...hijos.flat().filter(x => x != null)); return e;
};
const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + ' M' : n >= 1e3 ? Math.round(n / 1e3) + ' mil' : String(Math.round(n));
const mb = b => (b / 1048576).toFixed(1) + ' MB';

const app = $('#app'), lienzo = $('#lienzo');
if (window.Capacitor?.isNativePlatform?.()) app.classList.add('nativo');
const visor = new Visor(lienzo, {alSeleccion: m => alSeleccion(m)});
const camera = visor.camera;

let escena = null, etiquetas = {}, modo = null;            // modo: null | 'medir'
let medida = [], medidaAyudas = [], medidaPuntos = [];
let fps = 0, cuadros = 0, t0 = performance.now(), distInfo = 0;

// ------------------------------------------------------------------ navegación
const nav = new Navegacion(camera, lienzo, {
  alCambiar: () => visor.pedir(),
  puntoEn: (x, y) => visor.puntoEn(x, y),
  alInteractuar: a => { visor.interactuando(a); if (!a) visor.marcaPivote(nav.mira, false); else if (nav.modo === 'orbitar') visor.marcaPivote(nav.mira, true); },
  alModo: m => marcarModo(m),
  alTocar: (x, y) => tocar(x, y),
});
nav.fijarModelo(visor.caja);
nav.encuadrar(visor.caja, new THREE.Vector3(1, 0.8, 1), false);

function tocar(x, y) {
  if (modo === 'medir') {
    const p = visor.puntoEn(x, y); if (!p) return;
    if (medida.length >= 2) limpiarMedida();
    medida.push(p); medidaPuntos.push(visor.punto(p));
    if (medida.length === 2) {
      medidaAyudas.push(visor.linea(medida[0], medida[1]));
      const d = medida[0].distanceTo(medida[1]);
      const l = $('#mlabel'); l.hidden = false; l.textContent = d >= 1 ? d.toFixed(2) + ' m' : (d * 100).toFixed(1) + ' cm';
    }
    return;
  }
  visor.seleccionar(visor.mallaEn(x, y));
}
function limpiarMedida() {
  medida = []; [...medidaAyudas, ...medidaPuntos].forEach(h => { visor.ayudas.remove(h); h.geometry.dispose(); h.material.dispose(); });
  medidaAyudas = []; medidaPuntos = []; $('#mlabel').hidden = true; visor.pedir();
}

// ------------------------------------------------------------------ bucle
let ultimo = performance.now();
function bucle(ahora) {
  const dt = Math.min(0.1, (ahora - ultimo) / 1000); ultimo = ahora;
  if (nav.actualizar(dt)) visor.pedir();
  if (visor.dibujar()) { cuadros++; actualizarMarcas(); }
  if (ahora - t0 > 1000) { fps = cuadros * 1000 / (ahora - t0); cuadros = 0; t0 = ahora; infoTxt(); }
  requestAnimationFrame(bucle);
}
function actualizarMarcas() {
  distInfo = nav.distancia();
  if (medida.length === 2) {
    const a = visor.aPantalla(medida[0].clone().lerp(medida[1], 0.5)), l = $('#mlabel');
    l.style.left = a.x + 'px'; l.style.top = a.y + 'px'; l.style.display = a.ok ? '' : 'none';
  }
}
function infoTxt() {
  $('#info').textContent = escena ? `${escena.nombre} · ${fmt(visor.triangulos)} tri · ${fps > 0 ? fps.toFixed(0) + ' fps' : 'en reposo'} · pivote ${distInfo.toFixed(1)} m` : 'NavisMobile';
}

// ------------------------------------------------------------------ pestañas
function abrirPanel(id) {
  $$('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.p === id));
  $$('.pane').forEach(p => p.classList.toggle('on', p.id === id));
}
$$('.tabs button').forEach(b => b.onclick = () => abrirPanel(b.dataset.p));
$('#bUi').onclick = () => { app.classList.toggle('clean'); setTimeout(() => visor.ajustar(), 50); };

// ------------------------------------------------------------------ escenas
const progreso = (txt, a, b) => {
  const c = $('#carga'); c.hidden = false; $('#cargaTxt').textContent = txt;
  $('#cargaBar i').style.width = b ? Math.min(100, a / b * 100) + '%' : '30%';
};
async function pintarEscenas() {
  const cont = $('#escenas'); cont.textContent = '';
  let cat;
  try { cat = await datos.catalogo(); } catch (e) { cont.append(el('p', {className: 'nota', textContent: 'No se pudo leer el catálogo: ' + e.message})); return; }
  for (const esc of cat.escenas) {
    const tarjeta = el('div', {className: 'tarjeta'}, el('h3', {textContent: esc.nombre}), el('p', {textContent: esc.descripcion || ''}));
    for (const m of esc.modelos) {
      const ops = el('div', {className: 'ops'});
      const est = el('div', {className: 'estado'});
      const abrir = el('button', {textContent: `Abrir ${m.nombre}`, onclick: () => abrirEscena(esc, m)});
      ops.append(abrir);
      if (!m.archivo.ruta) {
        ops.append(el('button', {textContent: 'Actualizar', onclick: async () => { await abrirEscena(esc, m, true); pintarEscenas(); }}),
                   el('button', {textContent: 'Borrar descarga', onclick: async () => { await datos.borrar(m.archivo); pintarEscenas(); }}));
      }
      tarjeta.append(ops, est);
      datos.comprobar(m.archivo).then(s => {
        est.className = 'estado ' + (s === 'cambio' ? 'av' : 'ok');
        est.textContent = {local: 'Incluido en la app', al_dia: `Descargado (${mb(datos.tamano(m.archivo))}) · al día`, cambio: 'Hay una versión nueva',
          sin_conexion: 'Descargado · sin conexión para comprobar', no_descargado: `Sin descargar (${mb(m.archivo.bytes || 0)})`}[s] || s;
      });
    }
    cont.append(tarjeta);
  }
  const f = el('input', {type: 'file', accept: '.glb', hidden: true, onchange: async () => {
    const a = f.files[0]; if (!a) return;
    await cargarBuffer({id: 'local', nombre: a.name}, await a.arrayBuffer());
  }});
  cont.append(el('div', {className: 'tarjeta'}, el('h3', {textContent: 'Archivo del teléfono'}), el('div', {className: 'ops'},
    el('button', {textContent: 'Abrir GLB del teléfono', onclick: () => f.click()})), f));
}

async function abrirEscena(esc, modelo, forzar = false) {
  try {
    progreso('Preparando…', 0, 0);
    const buf = await datos.obtener(modelo.archivo, {forzar, progreso: (a, b) => progreso(`Descargando ${modelo.archivo.nombre}`, a, b)});
    etiquetas = {};
    if (esc.etiquetas) { try { etiquetas = await datos.obtenerJson(esc.etiquetas); } catch { /* sin etiquetas */ } }
    await cargarBuffer(esc, buf);
  } catch (e) {
    console.error(e); alert('No se pudo abrir la escena: ' + e.message);
  } finally { $('#carga').hidden = true; }
}
async function cargarBuffer(esc, buf) {
  progreso('Procesando modelo…', 0, 0);
  await new Promise(r => setTimeout(r, 30));
  limpiarMedida(); escena = esc;
  if (esc.id === 'local') etiquetas = {};
  const r = await visor.cargar(buf);
  nav.fijarModelo(r.caja); nav.encuadrar(visor.cajaNucleo(), new THREE.Vector3(1, 0.8, 1), false);
  ajustarCorte(); pintarCapas(); pintarVistas(); pintarAnim();
  $('#props').textContent = 'Toque un objeto para ver sus propiedades.';
  $('#carga').hidden = true; infoTxt(); abrirPanel('capas');
  if (window.matchMedia('(max-width:700px)').matches) { /* en móvil el panel ocupa poco: se deja abierto */ }
}

// ------------------------------------------------------------------ capas
let filtro = '';
function tagDe(m) { return m.userData.tag || m.userData.nodo || m.name.replace(/_\d+$/, ''); }
function pintarCapas() {
  const cont = $('#capas'); cont.textContent = '';
  if (!visor.mallas.length) { cont.textContent = 'Abra una escena primero.'; return; }
  const buscar = el('input', {type: 'search', placeholder: `Buscar entre ${visor.mallas.length} objetos (TAG)…`, value: filtro,
    style: 'width:100%;box-sizing:border-box;margin-bottom:6px', oninput: e => { filtro = e.target.value.toLowerCase(); lista(); }});
  const cuerpo = el('div'); cont.append(buscar, cuerpo);
  function lista() {
    cuerpo.textContent = '';
    visor.mallas.forEach(m => {
      const tag = tagDe(m); if (filtro && !tag.toLowerCase().includes(filtro)) return;
      const c = m.material.color || new THREE.Color(0x888888);
      const it = el('div', {className: 'item' + (visor.seleccion === m ? ' sel' : ''), onclick: () => visor.seleccionar(m)},
        el('input', {type: 'checkbox', checked: m.visible, onclick: e => e.stopPropagation(), onchange: e => visor.mostrar(m, e.target.checked)}),
        el('span', {className: 'sw', style: `background:#${c.getHexString()}`}),
        el('div', {className: 'gr'}, el('div', {textContent: tag}), el('small', {textContent: `${fmt(m.userData.tri)} tri`})));
      it.dataset.i = m.userData.idx; cuerpo.append(it);
    });
  }
  lista(); cont._lista = lista;
}
function alSeleccion(m) {
  $$('#capas .item').forEach(i => i.classList.toggle('sel', !!m && Number(i.dataset.i) === m.userData.idx));
  const sel = $('#capas .item.sel'); sel?.scrollIntoView({block: 'nearest'});
  pintarProps(m);
  if (m) $('#props').dispatchEvent(new Event('mostrar'));
}

// ------------------------------------------------------------------ propiedades
function pintarProps(m) {
  const cont = $('#props'); cont.textContent = '';
  if (!m) { cont.textContent = 'Toque un objeto para ver sus propiedades.'; return; }
  const tag = tagDe(m), ext = etiquetas[tag] || etiquetas[m.name] || {};
  const filas = [['TAG', tag]];
  for (const [k, v] of Object.entries({...m.userData, ...ext})) {
    if (['idx', 'tri', 'matOrig', 'name'].includes(k) || v === '' || v == null || typeof v === 'object') continue;
    if (k === 'tag' || k === 'ruta') continue;
    filas.push([k.replace(/^Elemento - /, ''), String(v)]);
  }
  const ruta = m.userData.ruta || ext.ruta; if (ruta) filas.splice(1, 0, ['Ruta', String(ruta).replace(/ \/ /g, ' › ')]);
  const b = visor.cajaDe(m), s = b.getSize(new THREE.Vector3());
  filas.push(['Triángulos', fmt(m.userData.tri)], ['Dimensiones (m)', `${s.x.toFixed(2)} × ${s.z.toFixed(2)} × ${s.y.toFixed(2)}`]);
  if (m.userData.matOrig?.color) filas.push(['Color', '#' + m.userData.matOrig.color.getHexString()]);
  cont.append(el('div', {className: 'cat', textContent: 'Elemento'}));
  for (const [k, v] of filas) cont.append(el('div', {className: 'row'}, el('b', {textContent: k}), el('span', {textContent: v})));
  cont.append(el('div', {className: 'ops', style: 'margin-top:8px;display:flex;gap:6px'},
    el('button', {textContent: 'Encuadrar', onclick: () => nav.encuadrar(b)}),
    el('button', {textContent: 'Aislar', onclick: () => visor.aislar(m)})));
}

// ------------------------------------------------------------------ barra
const seleccionados = () => visor.seleccion;
$('#bIso').onclick = () => { const m = seleccionados(); if (m) { visor.aislar(m); pintarCapas(); } };
$('#bHide').onclick = () => { const m = seleccionados(); if (m) { visor.mostrar(m, false); pintarCapas(); } };
$('#bShow').onclick = () => { visor.mostrarTodo(); pintarCapas(); };
$('#bFit').onclick = () => { nav.recordar(); nav.encuadrar(visor.seleccion ? visor.cajaDe(visor.seleccion) : visor.cajaVisible()); };
$('#bUndo').onclick = () => nav.deshacer();
$('#bMeas').onclick = e => {
  modo = modo === 'medir' ? null : 'medir'; e.currentTarget.classList.toggle('on', modo === 'medir');
  if (!modo) limpiarMedida();
};

// ------------------------------------------------------------------ corte
let ejeCorte = null, invCorte = false;
const cortar = () => {
  if (!ejeCorte) { visor.cortar(null); $('#clipVal').textContent = ''; return; }
  const pos = visor.cortar(ejeCorte, $('#clipPos').value / 1000, invCorte);
  $('#clipVal').textContent = pos.toFixed(1) + ' m';
};
function ajustarCorte() { if (ejeCorte) cortar(); }
$('#bClip').onclick = e => {
  const c = $('#clip'); c.hidden = !c.hidden; e.currentTarget.classList.toggle('on', !c.hidden);
  if (c.hidden) { ejeCorte = null; $$('#clip [data-a]').forEach(b => b.classList.remove('on')); } else { ejeCorte = ejeCorte || 'y'; }
  $$('#clip [data-a]').forEach(b => b.classList.toggle('on', b.dataset.a === ejeCorte)); cortar();
};
$$('#clip [data-a]').forEach(b => b.onclick = () => { ejeCorte = b.dataset.a; $$('#clip [data-a]').forEach(x => x.classList.toggle('on', x === b)); cortar(); });
$('#clipPos').oninput = cortar;
$('#clipFlip').onclick = () => { invCorte = !invCorte; cortar(); };

// ------------------------------------------------------------------ vistas
const VISTAS = [['planta', 'Planta'], ['frente', 'Frente'], ['atras', 'Atrás'], ['izquierda', 'Izquierda'], ['derecha', 'Derecha'], ['iso', 'Isométrica']];
const claveVistas = () => `navismobile-vistas-${escena?.id || 'x'}`;
const leerVistas = () => { try { return JSON.parse(localStorage.getItem(claveVistas()) || '[]'); } catch { return []; } };
function pintarVistas() {
  const c = $('#vistas'); c.textContent = '';
  VISTAS.forEach(([k, n]) => c.append(el('div', {className: 'item', textContent: n, onclick: () => nav.vista(k, visor.cajaVisible())})));
  c.append(el('div', {className: 'cat', textContent: 'Mis vistas'}));
  const vs = leerVistas();
  vs.forEach((v, i) => c.append(el('div', {className: 'item'}, el('div', {className: 'gr', textContent: v.nombre, onclick: () => { nav.recordar(); nav.aplicar(v.e, true); }}),
    el('button', {textContent: '✕', onclick: () => { vs.splice(i, 1); localStorage.setItem(claveVistas(), JSON.stringify(vs)); pintarVistas(); }}))));
  c.append(el('button', {textContent: 'Guardar vista actual', onclick: () => {
    const n = prompt('Nombre de la vista', `Vista ${vs.length + 1}`); if (!n) return;
    vs.push({nombre: n, e: nav.estado()}); localStorage.setItem(claveVistas(), JSON.stringify(vs)); pintarVistas();
  }}));
}
function pintarAnim() {
  $('#anim').textContent = '';
  $('#anim').append(el('p', {className: 'nota', textContent: 'Esta escena no tiene recorridos ni animaciones todavía.'}));
}

// ------------------------------------------------------------------ panel de navegación
function marcarModo(m) { $$('#modos [data-m]').forEach(b => b.classList.toggle('on', b.dataset.m === m)); mostrarCaminar(m === 'caminar'); }
function mostrarCaminar(v) { $('#palanca').hidden = !v; $('#vert').hidden = !v; $('#filaVel').style.display = v ? '' : 'none'; }
$$('#modos [data-m]').forEach(b => b.onclick = () => { nav.fijarModo(b.dataset.m); marcarModo(b.dataset.m); });
$('#bFino').onclick = () => { $('#fino').hidden = !$('#fino').hidden; };
$('#sens').oninput = e => { nav.sens = +e.target.value; $('#sensVal').textContent = nav.sens.toFixed(2) + '×'; };
$('#fov').oninput = e => { camera.fov = +e.target.value; camera.updateProjectionMatrix(); $('#fovVal').textContent = camera.fov + '°'; visor.pedir(); };
$('#vel').oninput = e => { nav.velocidad = +e.target.value; $('#velVal').textContent = nav.velocidad + ' m/s'; };
$$('#fino [data-g]').forEach(b => b.onclick = () => {
  const p = THREE.MathUtils.degToRad(+$('#pasoG').value); nav.recordar();
  const [dg, dc] = {izq: [p, 0], der: [-p, 0], arr: [0, -p], aba: [0, p]}[b.dataset.g];
  nav.girar(dg, dc, nav.modo === 'caminar');
});
$$('#fino [data-d]').forEach(b => b.onclick = () => {
  const p = +$('#pasoM').value; nav.recordar();
  const [x, y, z] = {ade: [0, 0, p], atr: [0, 0, -p], izq: [-p, 0, 0], der: [p, 0, 0], sub: [0, p, 0], baj: [0, -p, 0]}[b.dataset.d];
  nav.mover(x, y, z);
});
// joystick de caminar
{
  const pal = $('#palanca'), per = $('#perilla'); let activo = null;
  const poner = e => {
    const r = pal.getBoundingClientRect(), R = r.width / 2;
    let dx = e.clientX - (r.left + R), dy = e.clientY - (r.top + R); const l = Math.hypot(dx, dy);
    if (l > R) { dx *= R / l; dy *= R / l; }
    per.style.transform = `translate(${dx}px,${dy}px)`; nav.palanca.set(dx / R, dy / R);
  };
  pal.addEventListener('pointerdown', e => { activo = e.pointerId; pal.setPointerCapture(activo); poner(e); });
  pal.addEventListener('pointermove', e => { if (e.pointerId === activo) poner(e); });
  const fin = e => { if (e.pointerId !== activo) return; activo = null; per.style.transform = ''; nav.palanca.set(0, 0); };
  pal.addEventListener('pointerup', fin); pal.addEventListener('pointercancel', fin);
  $$('#vert [data-v]').forEach(b => {
    b.addEventListener('pointerdown', e => { b.setPointerCapture(e.pointerId); nav.vertical = +b.dataset.v; });
    const f = () => { nav.vertical = 0; }; b.addEventListener('pointerup', f); b.addEventListener('pointercancel', f);
  });
}
mostrarCaminar(false);

// ------------------------------------------------------------------ arranque
window.__nm = {visor, nav, abrirEscena, cargarBuffer};      // ayuda para pruebas
pintarEscenas();
requestAnimationFrame(bucle);
