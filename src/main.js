import * as THREE from 'three';
import { Visor } from './visor.js';
import { Navegacion } from './navegacion.js';
import { Equipos } from './equipos.js';
import { Correas } from './correas.js';
import { Recorrido } from './recorridos.js';
import { obtener, obtenerJSON, comprobar, borrar, tamano, mb, persistir } from './datos.js';

const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const ht = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const visor = new Visor($('#lienzo'));
window.visor = visor;
const nav = new Navegacion(visor.camera, $('#lienzo'), {
  alCambiar: () => visor.invalidar(),
  puntoEn: (x, y) => visor.puntoEn(x, y),
  alTocar: (x, y) => tocar(x, y),
  alInteractuar: (a) => { visor.interactuando(a); marca.visible = a && nav.modo === 'orbitar'; visor.invalidar(); },
  alModo: (m) => marcarModo(m),
});
window.nav = nav;

const E = { cat: null, escena: null, modelo: null, equipos: null, correas: null, recorrido: null, anim: null, tAnim: 0, reproAnim: false,
            sel: null, medir: false, puntosMedida: [], corte: { eje: 'x', inv: false, on: false } };
window.E = E;

// ------------------------------------------------------------------ ayudantes (capa 1)
const marca = new THREE.Mesh(new THREE.SphereGeometry(1, 12, 8), new THREE.MeshBasicMaterial({ color: 0x4aa3ff, depthTest: false, transparent: true, opacity: 0.8 }));
marca.layers.set(1); marca.visible = false; marca.renderOrder = 10; visor.ayudantes.add(marca);
const cajaSel = new THREE.Box3Helper(new THREE.Box3(), 0xffd24a); cajaSel.layers.set(1); cajaSel.visible = false; visor.ayudantes.add(cajaSel);
const lineaMed = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: 0xffd24a, depthTest: false }));
lineaMed.layers.set(1); lineaMed.visible = false; lineaMed.renderOrder = 11; lineaMed.frustumCulled = false; visor.ayudantes.add(lineaMed);

// ------------------------------------------------------------------ carga
function carga(txt, frac) {
  const c = $('#carga'); c.hidden = txt == null; if (txt == null) return;
  $('#cargaTxt').textContent = txt; $('#cargaBar i').style.width = Math.round((frac || 0) * 100) + '%';
}
const prog = (nombre) => (n, t) => carga(`${nombre}: ${mb(n)}${t ? ' / ' + mb(t) : ''}`, t ? n / t : 0);

async function abrirBuffer(buf, titulo, escena = null, modelo = null) {
  limpiar(); E.escena = escena; E.modelo = modelo;
  carga('Preparando modelo…', 1);
  await visor.cargar(buf);
  nav.fijarModelo(visor.caja); nav.encuadrar(visor.caja, new THREE.Vector3(1, 0.8, 1), false);
  nav.historial = [];
  if (escena) await cargarExtras(escena);
  actualizarCapas(); mostrarProps(null); renderVistas(); renderAnim();
  $('#info').textContent = titulo; carga(null); visor.invalidar(); marcarTab('capas');
}
function limpiar() {
  if (E.recorrido) E.recorrido.detener();
  if (E.correas) { visor.ayudantes.remove(E.correas.grupo); }
  E.equipos = E.correas = E.recorrido = E.anim = null; E.reproAnim = false; seleccionar(null); cancelarMedida(); activarCorte(false);
}
async function cargarExtras(esc) {
  try {
    if (esc.escena) {
      const j = await obtenerJSON(esc.escena, { progreso: prog(esc.escena.nombre) });
      const s = j.soles?.[0]; if (s) visor.fijarSol(s.hacia_sol_three, s.energia);
      if (j.camara?.lente_mm) { const f = 2 * Math.atan((j.camara.sensor_mm || 36) / (2 * j.camara.lente_mm)) * 180 / Math.PI; visor.camera.fov = THREE.MathUtils.clamp(f, 15, 100); nav._listo(); }
    }
    if (esc.correas) { E.correas = new Correas(await obtenerJSON(esc.correas)); visor.ayudantes.add(E.correas.grupo); }
    if (esc.equipos) {
      const json = await obtenerJSON(esc.equipos.json), bin = await obtener(esc.equipos.bin, { progreso: prog('Equipos') });
      E.equipos = new Equipos(json, bin); visor.raiz.add(E.equipos.grupo); visor.actualizarMallas();
      if (esc.animaciones) E.equipos.cargarAnimaciones(await obtenerJSON(esc.animaciones));
    }
  } catch (e) { console.warn('Datos adicionales no disponibles:', e); $('#info').textContent = 'Aviso: ' + e.message; }
}

// ------------------------------------------------------------------ pestañas
function marcarTab(id) {
  $$('.tabs button').forEach((b) => b.classList.toggle('on', b.dataset.p === id));
  $$('.pane').forEach((p) => p.classList.toggle('on', p.id === id));
}
$$('.tabs button').forEach((b) => b.onclick = () => marcarTab(b.dataset.p));
$('#bUi').onclick = () => $('#app').classList.toggle('clean');

// ------------------------------------------------------------------ escenas
const textoEstado = { no_descargado: ['No descargado', ''], al_dia: ['Descargado ✓', 'ok'], cambio: ['Hay versión nueva', 'av'], sin_conexion: ['Descargado (sin conexión)', 'ok'] };
async function renderEscenas() {
  const p = $('#escenas'); p.innerHTML = '';
  for (const esc of E.cat.escenas) {
    const t = document.createElement('div'); t.className = 'tarjeta';
    t.innerHTML = `<h3>${ht(esc.nombre)}</h3><p>${ht(esc.descripcion)}</p>`;
    for (const mo of esc.modelos) {
      const f = document.createElement('div'); f.className = 'item';
      f.innerHTML = `<div class="gr"><b>${ht(mo.nombre)}</b>${mo.pesado ? ' ⚠' : ''}<small class="estado">…</small></div><button data-o="a">Abrir</button><button data-o="u">Actualizar</button><button data-o="b">Borrar</button>`;
      t.appendChild(f);
      const est = $('.estado', f);
      const refrescar = async () => { const s = await comprobar(mo.archivo), [tx, cl] = textoEstado[s]; est.textContent = `${tx} · ${mb(tamano(mo.archivo))}`; est.className = 'estado ' + cl; return s; };
      refrescar();
      $('[data-o=a]', f).onclick = async () => {
        if (mo.pesado && !confirm('Modelo de alta calidad: usa mucha memoria y puede cerrar la app en teléfonos modestos. ¿Continuar?')) return;
        await abrir(esc, mo); refrescar();
      };
      $('[data-o=u]', f).onclick = async () => { try { await obtener(mo.archivo, { forzar: true, progreso: prog(mo.nombre) }); } catch (e) { alert(e.message); } carga(null); refrescar(); };
      $('[data-o=b]', f).onclick = async () => { await borrar(mo.archivo); refrescar(); };
    }
    p.appendChild(t);
  }
  const loc = document.createElement('div'); loc.className = 'tarjeta';
  loc.innerHTML = '<h3>Abrir GLB del teléfono</h3><p>Cargue un archivo .glb local.</p><input type="file" accept=".glb,.gltf,model/gltf-binary">';
  $('input', loc).onchange = async (e) => { const f = e.target.files[0]; if (f) await abrirBuffer(await f.arrayBuffer(), f.name); };
  p.appendChild(loc);
}
async function abrir(esc, mo) {
  try {
    const buf = await obtener(mo.archivo, { progreso: prog(mo.nombre) });
    await abrirBuffer(buf, `${esc.nombre} — ${mo.nombre}`, esc, mo);
  } catch (e) { carga(null); alert('No se pudo abrir: ' + e.message); }
}

// ------------------------------------------------------------------ capas / propiedades
function actualizarCapas() {
  const p = $('#capas'); p.innerHTML = '';
  visor.mallas.forEach((m) => {
    const c = m.material.color ? '#' + m.material.color.getHexString() : '#888';
    const it = document.createElement('div'); it.className = 'item'; it.dataset.i = m.userData.idx;
    it.innerHTML = `<input type="checkbox" ${m.visible ? 'checked' : ''}><span class="sw" style="background:${c}"></span><div class="gr">${ht(m.name || 'malla ' + m.userData.idx)}<small>${m.userData.tris.toLocaleString('es')} triángulos</small></div>`;
    $('input', it).onclick = (e) => { e.stopPropagation(); m.visible = e.target.checked; visor.invalidar(); };
    it.onclick = () => seleccionar(m);
    p.appendChild(it);
  });
}
function seleccionar(m) {
  E.sel = m; $$('#capas .item').forEach((i) => i.classList.toggle('sel', m && +i.dataset.i === m.userData.idx));
  if (m) { cajaSel.box.setFromObject(m); cajaSel.visible = true; } else cajaSel.visible = false;
  mostrarProps(m); visor.invalidar();
}
function mostrarProps(m) {
  const p = $('#props'); if (!m) { p.textContent = 'Toque un objeto para ver sus propiedades.'; return; }
  const mat = m.material, s = new THREE.Box3().setFromObject(m).getSize(new THREE.Vector3());
  const f = (n) => n.toFixed(2) + ' m', fila = (k, v) => `<div class="row"><b>${k}</b><span>${ht(v)}</span></div>`;
  p.innerHTML = fila('Nombre', m.name || '—') + fila('Material', mat.name || mat.type) + fila('Triángulos', m.userData.tris.toLocaleString('es'))
    + fila('Dimensiones', `${f(s.x)} × ${f(s.y)} × ${f(s.z)}`) + (mat.color ? fila('Color', '#' + mat.color.getHexString()) : '')
    + (mat.metalness != null ? fila('Metal / rugosidad', `${mat.metalness.toFixed(2)} / ${mat.roughness.toFixed(2)}`) : '');
}
function tocar(x, y) {
  if (E.medir) return medirPunto(x, y);
  const m = visor.mallaEn(x, y); seleccionar(m);
}

// ------------------------------------------------------------------ barra
const alternar = (id, on) => $(id).classList.toggle('on', on);
$('#bIso').onclick = () => { if (!E.sel) return; visor.mallas.forEach((m) => (m.visible = m === E.sel)); actualizarCapas(); seleccionar(E.sel); };
$('#bHide').onclick = () => { if (E.sel) { E.sel.visible = false; actualizarCapas(); seleccionar(null); } };
$('#bShow').onclick = () => { visor.mallas.forEach((m) => (m.visible = true)); actualizarCapas(); visor.invalidar(); };
$('#bFit').onclick = () => { nav.recordar(); nav.encuadrar(E.sel ? new THREE.Box3().setFromObject(E.sel) : visor.caja); };
$('#bUndo').onclick = () => nav.deshacer();

// Corte
function aplicarCorte() {
  if (!E.corte.on) return visor.corte(null);
  const { eje, inv } = E.corte, i = { x: 0, y: 1, z: 2 }[eje], b = visor.caja;
  const pos = b.min.getComponent(i) + (b.max.getComponent(i) - b.min.getComponent(i)) * $('#clipPos').value / 1000;
  const n = new THREE.Vector3().setComponent(i, inv ? -1 : 1);
  visor.corte(new THREE.Plane(n, inv ? pos : -pos)); $('#clipVal').textContent = `${eje.toUpperCase()} = ${pos.toFixed(1)} m`;
}
function activarCorte(on) { E.corte.on = on; $('#clip').hidden = !on; alternar('#bClip', on); aplicarCorte(); }
$('#bClip').onclick = () => activarCorte(!E.corte.on);
$$('#clip [data-a]').forEach((b) => b.onclick = () => { E.corte.eje = b.dataset.a; aplicarCorte(); });
$('#clipPos').oninput = aplicarCorte;
$('#clipFlip').onclick = () => { E.corte.inv = !E.corte.inv; aplicarCorte(); };

// Medir
const lbl = $('#mlabel');
function cancelarMedida() { E.puntosMedida = []; lineaMed.visible = false; lbl.hidden = true; }
$('#bMeas').onclick = () => { E.medir = !E.medir; alternar('#bMeas', E.medir); cancelarMedida(); };
function medirPunto(x, y) {
  const q = visor.puntoEn(x, y); if (!q) return;
  if (E.puntosMedida.length >= 2) cancelarMedida();
  E.puntosMedida.push(q);
  if (E.puntosMedida.length === 2) {
    lineaMed.geometry.setFromPoints(E.puntosMedida); lineaMed.visible = true;
    lbl.textContent = E.puntosMedida[0].distanceTo(E.puntosMedida[1]).toFixed(3) + ' m'; lbl.hidden = false;
  }
  visor.invalidar();
}
function posEtiqueta() {
  if (lbl.hidden || E.puntosMedida.length < 2) return;
  const m = E.puntosMedida[0].clone().add(E.puntosMedida[1]).multiplyScalar(0.5).project(visor.camera);
  lbl.style.left = (m.x * 0.5 + 0.5) * $('#lienzo').clientWidth + 'px'; lbl.style.top = (-m.y * 0.5 + 0.5) * $('#lienzo').clientHeight + 'px';
}

// ------------------------------------------------------------------ navegación
function marcarModo(m) { $$('#modos [data-m]').forEach((b) => b.classList.toggle('on', b.dataset.m === m)); $('#palanca').hidden = $('#vert').hidden = m !== 'caminar'; $('#filaVel').hidden = m !== 'caminar'; }
$$('#modos [data-m]').forEach((b) => b.onclick = () => { nav.fijarModo(b.dataset.m); marcarModo(b.dataset.m); });
$('#bFino').onclick = () => { $('#fino').hidden = !$('#fino').hidden; alternar('#bFino', !$('#fino').hidden); };
$('#sens').oninput = (e) => { nav.sens = +e.target.value; $('#sensVal').textContent = (+e.target.value).toFixed(2) + '×'; };
$('#fov').oninput = (e) => { visor.camera.fov = +e.target.value; $('#fovVal').textContent = e.target.value + '°'; nav._listo(); };
$('#vel').oninput = (e) => { nav.velocidad = +e.target.value; $('#velVal').textContent = e.target.value + ' m/s'; };
const rad = (g) => g * Math.PI / 180;
$$('#fino [data-g]').forEach((b) => b.onclick = () => {
  const a = rad(+$('#pasoG').value); nav.recordar();
  ({ izq: () => nav.girar(-a, 0), der: () => nav.girar(a, 0), arr: () => nav.girar(0, a), aba: () => nav.girar(0, -a) })[b.dataset.g]();
});
$$('#fino [data-d]').forEach((b) => b.onclick = () => {
  const s = +$('#pasoM').value; nav.recordar();
  const [dx, dy, dz] = { ade: [0, 0, s], atr: [0, 0, -s], izq: [-s, 0, 0], der: [s, 0, 0], sub: [0, s, 0], baj: [0, -s, 0] }[b.dataset.d];
  nav.mover(dx, dy, dz);
});
// Palanca de caminar
{
  const pl = $('#palanca'), pe = $('#perilla'); let id = null;
  const mover = (e) => {
    const r = pl.getBoundingClientRect(), R = r.width / 2;
    let dx = (e.clientX - r.left - R) / R, dy = (e.clientY - r.top - R) / R; const l = Math.hypot(dx, dy); if (l > 1) { dx /= l; dy /= l; }
    nav.palanca.set(dx, dy); pe.style.transform = `translate(${dx * R * 0.6}px,${dy * R * 0.6}px)`;
  };
  pl.onpointerdown = (e) => { id = e.pointerId; pl.setPointerCapture(id); mover(e); };
  pl.onpointermove = (e) => { if (e.pointerId === id) mover(e); };
  pl.onpointerup = pl.onpointercancel = () => { id = null; nav.palanca.set(0, 0); pe.style.transform = ''; };
  $$('#vert [data-v]').forEach((b) => { b.onpointerdown = () => (nav.vertical = +b.dataset.v); b.onpointerup = b.onpointerleave = b.onpointercancel = () => (nav.vertical = 0); });
}

// ------------------------------------------------------------------ vistas
const VISTAS = [['planta', 'Planta'], ['frente', 'Frente'], ['atras', 'Atrás'], ['izquierda', 'Izquierda'], ['derecha', 'Derecha'], ['iso', 'Iso']];
const claveVistas = () => 'vistas:' + (E.escena?.id || 'local');
function renderVistas() {
  const p = $('#vistas'); p.innerHTML = '<div class="cat">Vistas estándar</div><div class="ops"></div><div class="cat">Mis vistas</div><div id="misVistas"></div><button id="bGuardar">Guardar vista actual</button>';
  VISTAS.forEach(([k, n]) => { const b = document.createElement('button'); b.textContent = n; b.onclick = () => nav.vista(k); $('.ops', p).appendChild(b); });
  $('#bGuardar').onclick = () => { const n = prompt('Nombre de la vista'); if (!n) return; const l = JSON.parse(localStorage.getItem(claveVistas()) || '[]'); l.push({ n, e: nav.estado() }); localStorage.setItem(claveVistas(), JSON.stringify(l)); pintarMias(); };
  pintarMias();
}
function pintarMias() {
  const l = JSON.parse(localStorage.getItem(claveVistas()) || '[]'), c = $('#misVistas'); c.innerHTML = '';
  l.forEach((v, i) => {
    const it = document.createElement('div'); it.className = 'item'; it.innerHTML = `<div class="gr">${ht(v.n)}</div><button>✕</button>`;
    it.onclick = () => { nav.recordar(); nav.aplicar(v.e, true); };
    $('button', it).onclick = (e) => { e.stopPropagation(); l.splice(i, 1); localStorage.setItem(claveVistas(), JSON.stringify(l)); pintarMias(); };
    c.appendChild(it);
  });
}

// ------------------------------------------------------------------ animación
function renderAnim() {
  const p = $('#anim'); p.innerHTML = '';
  const esc0 = E.escena;
  if (!esc0) { p.textContent = 'Abra una escena del catálogo para ver sus recorridos y animaciones.'; return; }
  if (esc0.recorridos?.length) {
    p.insertAdjacentHTML('beforeend', `<div class="cat">Recorridos</div><div class="ctl"><select id="selRec">${esc0.recorridos.map((r, i) => `<option value="${i}">${ht(r.nombre)}</option>`).join('')}</select><button id="recPlay">▶</button><button id="recStop">■</button></div>
      <div class="ctl"><input id="recT" type="range" min="0" max="1000" value="0"><span id="recTxt">0 s</span></div>
      <div class="ctl"><span>Velocidad</span><input id="recV" type="range" min="0.25" max="2" step="0.25" value="1"><b id="recVv">1×</b></div>`);
    $('#recPlay').onclick = reproducirRec; $('#recStop').onclick = () => { E.recorrido?.detener(); $('#recPlay').textContent = '▶'; visor.invalidar(); };
    $('#recT').oninput = (e) => { if (E.recorrido) { E.recorrido.nav.bloqueada = true; E.recorrido.ir(e.target.value / 1000 * E.recorrido.duracion); aplicarCiclo(); $('#recTxt').textContent = E.recorrido.t.toFixed(1) + ' s'; } };
    $('#recV').oninput = (e) => { if (E.recorrido) E.recorrido.velocidad = +e.target.value; $('#recVv').textContent = e.target.value + '×'; };
  }
  if (E.equipos?.anims.length) {
    p.insertAdjacentHTML('beforeend', `<div class="cat">Animaciones de equipos</div>` + E.equipos.anims.map((a, i) => `<div class="item" data-a="${i}"><div class="gr">${ht(a.nombre)}<small>${ht(a.descripcion || '')} · ${a.duracion} s</small></div></div>`).join('')
      + `<div class="ctl"><button id="anPlay">▶ / ⏸</button><button id="anStop">■</button></div><div class="nota">Las pistas de cámara, disciplina, visibilidad y resplandor se ignoran en el modelo unido.</div>`);
    $$('#anim [data-a]').forEach((it) => it.onclick = () => { E.anim = E.equipos.anims[+it.dataset.a]; E.tAnim = 0; E.reproAnim = true; $$('#anim [data-a]').forEach((x) => x.classList.toggle('sel', x === it)); });
    $('#anPlay').onclick = () => { if (E.anim) E.reproAnim = !E.reproAnim; };
    $('#anStop').onclick = () => { E.reproAnim = false; E.tAnim = 0; if (E.anim) E.equipos.aplicar(E.anim, 0); visor.invalidar(); };
  }
  if (E.correas) {
    p.insertAdjacentHTML('beforeend', '<div class="cat">Correas</div><label class="ctl"><input type="checkbox" id="chkCor" checked> Correas en movimiento</label>');
    $('#chkCor').onchange = (e) => { E.correas.visible(e.target.checked); visor.invalidar(); };
  }
  if (!p.children.length) p.textContent = 'Esta escena no tiene recorridos ni animaciones.';
}
async function reproducirRec() {
  const r = E.escena.recorridos[+$('#selRec').value];
  if (E.recorrido && E.recorrido.reproduciendo) { E.recorrido.pausar(); $('#recPlay').textContent = '▶'; return; }
  if (!E.recorrido || E.recorrido.fuente !== r) {
    try { carga('Recorrido…', 0); E.recorrido = new Recorrido(await obtenerJSON(r, { progreso: prog(r.nombre) }), nav); E.recorrido.fuente = r; carga(null); }
    catch (e) { carga(null); return alert(e.message); }
  }
  E.recorrido.velocidad = +$('#recV').value; nav.recordar(); E.recorrido.reproducir(); $('#recPlay').textContent = '⏸';
}
function aplicarCiclo() {
  if (!E.equipos || !E.recorrido) return;
  const a = E.equipos.anims.find((x) => x.id === 'ciclo-completo'); if (a) E.equipos.aplicar(a, E.recorrido.tCiclo);
}

// ------------------------------------------------------------------ bucle
let tInfo = 0;
visor.alCuadro = (dt) => {
  let c = nav.actualizar(dt);
  if (E.recorrido?.actualizar(dt)) {
    c = true; aplicarCiclo();
    const t = $('#recT'); if (t) { t.value = E.recorrido.t / E.recorrido.duracion * 1000; $('#recTxt').textContent = E.recorrido.t.toFixed(1) + ' s'; }
    if (!E.recorrido.reproduciendo) { $('#recPlay').textContent = '▶'; nav.bloqueada = false; }
  }
  if (E.reproAnim && E.anim) {
    E.tAnim += dt; E.equipos.aplicar(E.anim, E.tAnim); c = true;
    if (E.anim.bucle !== 'bucle' && E.anim.bucle !== 'vaiven' && E.tAnim >= E.anim.duracion) E.reproAnim = false;
  }
  if (E.correas?.actualizar(dt)) c = true;
  if (marca.visible || c) { const d = nav.distancia(); marca.position.copy(nav.mira); marca.scale.setScalar(Math.max(0.02, d * 0.012)); }
  posEtiqueta();
  tInfo += dt; if (tInfo > 0.5 && E.escena !== undefined) { tInfo = 0; $('#info').dataset.s = ''; infoEstado(); }
  return c;
};
function infoEstado() {
  if (!visor.raiz) return;
  const base = E.escena ? `${E.escena.nombre} — ${E.modelo?.nombre}` : 'Modelo local';
  $('#info').textContent = `${base} · ${(visor.triangulos() / 1e6).toFixed(2)} M tri · ${visor.fps} fps · pivote ${nav.distancia().toFixed(1)} m`;
}

// ------------------------------------------------------------------ inicio
(async () => {
  persistir(); marcarModo('orbitar');
  try { E.cat = await (await fetch(import.meta.env.BASE_URL + 'catalogo.json')).json(); await renderEscenas(); }
  catch (e) { $('#escenas').textContent = 'No se pudo leer el catálogo: ' + e.message; }
  renderVistas(); renderAnim();
})();
