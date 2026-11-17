// Navegación táctil y de ratón: orbitar, panear, zoom dirigido, caminar y movimiento fino por pasos.
// La cámara se describe con su posición y un punto de mira («pivote» al orbitar). Eje vertical: +Y.
import * as THREE from 'three';

const ARRIBA = new THREE.Vector3(0, 1, 0);
const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), v3 = new THREE.Vector3();
const POLO = 0.5 * Math.PI - 0.002;          // límite de cabeceo (evita el volteo en los polos)

export class Navegacion {
  /**
   * @param camera THREE.PerspectiveCamera
   * @param dom elemento que recibe los gestos
   * @param o {alCambiar(), puntoEn(x,y)->Vector3|null, alTocar(x,y), alInteractuar(activo)}
   */
  constructor(camera, dom, o = {}) {
    this.camera = camera; this.dom = dom; this.o = o;
    this.mira = new THREE.Vector3();
    this.modo = 'orbitar';
    this.sens = 1;                // multiplicador de sensibilidad de los gestos
    this.velocidad = 4;           // m/s al caminar
    this.radio = 100;             // radio del modelo (para límites y planos de recorte)
    this.centro = new THREE.Vector3();
    this.caja = new THREE.Box3(new THREE.Vector3(-50, -50, -50), new THREE.Vector3(50, 50, 50));
    this.historial = [];
    this.bloqueada = false;       // true mientras un recorrido mueve la cámara
    this.palanca = new THREE.Vector2(); this.vertical = 0;
    this._punteros = new Map(); this._ancla = null; this._transicion = null; this._tocado = null;
    this._ultimoToque = 0; this._ultimoXY = [0, 0];
    this._eventos();
  }

  // ---------------------------------------------------------------- estado
  estado() { return {p: this.camera.position.toArray(), m: this.mira.toArray(), fov: this.camera.fov}; }
  aplicar(e, suave = false) {
    const p = new THREE.Vector3().fromArray(e.p), m = new THREE.Vector3().fromArray(e.m);
    if (suave) return this._animarA(p, m, e.fov);
    this.camera.position.copy(p); this.mira.copy(m);
    if (e.fov) { this.camera.fov = e.fov; }
    this._listo();
  }
  recordar() {
    const e = this.estado(), u = this.historial[this.historial.length - 1];
    if (u && JSON.stringify(u) === JSON.stringify(e)) return;
    this.historial.push(e); if (this.historial.length > 60) this.historial.shift();
  }
  deshacer() { const e = this.historial.pop(); if (e) this.aplicar(e, true); return !!e; }
  distancia() { return this.camera.position.distanceTo(this.mira); }

  fijarModelo(caja) {
    this.caja.copy(caja); caja.getCenter(this.centro);
    this.radio = Math.max(1, caja.getSize(v1).length() / 2);
  }
  fijarModo(m) {
    this.modo = m;
    if (m === 'caminar') {       // al caminar, la mira queda a corta distancia delante de la cámara
      const d = this.camera.getWorldDirection(v1);
      this.mira.copy(this.camera.position).addScaledVector(d, 2);
    }
    this._listo();
  }

  // ---------------------------------------------------------------- movimientos básicos
  /** Gira alrededor del pivote (o sobre la propia cámara si sobreSi). Ángulos en radianes. */
  girar(dGuiñada, dCabeceo, sobreSi = this.modo === 'caminar') {
    const cam = this.camera.position;
    const fijo = sobreSi ? cam : this.mira, movil = sobreSi ? this.mira : cam;
    const r = v1.copy(movil).sub(fijo), largo = r.length() || 1;
    let cabeceo = Math.asin(THREE.MathUtils.clamp(r.y / largo, -1, 1)), guiñada = Math.atan2(r.x, r.z);
    guiñada += dGuiñada;
    cabeceo = THREE.MathUtils.clamp(cabeceo + (sobreSi ? -dCabeceo : dCabeceo), -POLO, POLO);
    const c = Math.cos(cabeceo);
    movil.set(fijo.x + largo * c * Math.sin(guiñada), fijo.y + largo * Math.sin(cabeceo), fijo.z + largo * c * Math.cos(guiñada));
    this._listo();
  }
  /** Desplaza cámara y mira en el sistema de la cámara (derecha, arriba, adelante), en metros. */
  mover(dx, dy, dz, horizontal = false) {
    const ade = this.camera.getWorldDirection(v1);
    if (horizontal) { ade.y = 0; if (ade.lengthSq() < 1e-8) ade.set(0, 0, -1); ade.normalize(); }
    const der = v2.crossVectors(ade, ARRIBA).normalize();
    const arr = horizontal ? v3.copy(ARRIBA) : v3.crossVectors(der, ade).normalize();
    const d = new THREE.Vector3().addScaledVector(der, dx).addScaledVector(arr, dy).addScaledVector(ade, dz);
    this.camera.position.add(d); this.mira.add(d);
    this._listo();
  }
  /** Paneo en píxeles de pantalla: el punto bajo el dedo sigue al dedo (a la profundidad de la referencia). */
  panearPx(dxPx, dyPx, profundidad = this.distancia()) {
    const k = 2 * profundidad * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2) / this.dom.clientHeight;
    this.mover(-dxPx * k, dyPx * k, 0);
  }
  /** Zoom por factor (<1 acerca) manteniendo fijo en pantalla el punto «ancla». */
  zoom(factor, ancla = this.mira) {
    const cam = this.camera.position, d = cam.distanceTo(ancla);
    const min = 0.05, max = this.radio * 12;
    if (d * factor < min) factor = min / d; if (d * factor > max) factor = max / d;
    const a = v1.copy(ancla);
    cam.sub(a).multiplyScalar(factor).add(a);
    if (this.modo !== 'caminar') this.mira.sub(a).multiplyScalar(factor).add(a);
    else this.mira.copy(cam).add(this.camera.getWorldDirection(v2).multiplyScalar(2));
    this._listo();
  }
  /** Fija el pivote de órbita sin mover la imagen: la cámara pasa a mirar hacia el nuevo pivote con una transición. */
  fijarPivote(p, centrar = true) {
    if (!centrar) { this.mira.copy(p); this._listo(); return; }
    const dir = this.camera.getWorldDirection(new THREE.Vector3());
    const d = Math.max(0.2, v1.copy(p).sub(this.camera.position).dot(dir));
    this._animarA(p.clone().addScaledVector(dir, -d), p.clone());
  }

  // ---------------------------------------------------------------- vistas
  encuadrar(caja = this.caja, dir = null, suave = true) {
    const c = caja.getCenter(new THREE.Vector3()), r = Math.max(0.5, caja.getSize(v1).length() / 2);
    const fovV = THREE.MathUtils.degToRad(this.camera.fov), fovH = 2 * Math.atan(Math.tan(fovV / 2) * this.camera.aspect);
    const d = r / Math.sin(Math.min(fovV, fovH) / 2);
    const n = (dir ? dir.clone() : this.camera.position.clone().sub(this.mira)).normalize();
    if (n.lengthSq() < 1e-6) n.set(1, 0.7, 1).normalize();
    const p = c.clone().addScaledVector(n, d);
    if (this.modo === 'caminar') this.modo = 'orbitar', this.o.alModo?.('orbitar');
    suave ? this._animarA(p, c) : (this.camera.position.copy(p), this.mira.copy(c), this._listo());
  }
  vista(nombre, caja = this.caja) {
    const D = {planta: [0, 1, 0.0015], frente: [0, 0, 1], atras: [0, 0, -1], izquierda: [-1, 0, 0], derecha: [1, 0, 0],
               iso: [1, 0.8, 1], iso2: [-1, 0.8, -1]}[nombre];
    if (D) { this.recordar(); this.encuadrar(caja, new THREE.Vector3(...D)); }
  }

  // ---------------------------------------------------------------- bucle
  /** Llamar en cada cuadro; devuelve true si la cámara cambió. */
  actualizar(dt) {
    let cambio = false;
    const tr = this._transicion;
    if (tr) {
      tr.t = Math.min(1, tr.t + dt / tr.dur); const u = tr.t * tr.t * (3 - 2 * tr.t);
      this.camera.position.lerpVectors(tr.p0, tr.p1, u); this.mira.lerpVectors(tr.m0, tr.m1, u);
      if (tr.f1) { this.camera.fov = tr.f0 + (tr.f1 - tr.f0) * u; }
      if (tr.t >= 1) this._transicion = null;
      cambio = true;
    }
    if (!this.bloqueada && (this.palanca.lengthSq() > 1e-4 || this.vertical)) {
      const v = this.velocidad * dt;
      this.mover(this.palanca.x * v, this.vertical * v, -this.palanca.y * v, true);
      cambio = true;
    }
    if (cambio) this._listo(false);
    return cambio;
  }
  _animarA(p, m, fov) {
    this._transicion = {p0: this.camera.position.clone(), m0: this.mira.clone(), p1: p, m1: m, f0: this.camera.fov, f1: fov, t: 0, dur: 0.35};
    this.o.alCambiar?.();
  }
  _listo(avisar = true) {
    const cam = this.camera, d = this.distancia();
    cam.up.copy(ARRIBA); cam.lookAt(this.mira);
    const lejos = cam.position.distanceTo(this.centro) + this.radio * 1.5;
    cam.near = this.modo === 'caminar' ? 0.08 : THREE.MathUtils.clamp(d * 0.02, 0.05, lejos / 2000 + 0.5);
    cam.far = Math.max(lejos, cam.near * 100);
    cam.updateProjectionMatrix(); cam.updateMatrixWorld();
    if (avisar) this.o.alCambiar?.();
  }

  // ---------------------------------------------------------------- gestos
  _eventos() {
    const el = this.dom, P = this._punteros;
    const local = e => { const r = el.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    el.addEventListener('contextmenu', e => e.preventDefault());
    el.addEventListener('pointerdown', e => {
      if (this.bloqueada) { this.o.alTocar?.(...local(e), true); return; }
      el.setPointerCapture(e.pointerId);
      const [x, y] = local(e);
      P.set(e.pointerId, {x, y, x0: x, y0: y, boton: e.button, t: performance.now()});
      this._transicion = null; this.recordar();
      this._iniciarGesto(); this.o.alInteractuar?.(true);
    });
    el.addEventListener('pointermove', e => {
      const p = P.get(e.pointerId); if (!p || this.bloqueada) return;
      const [x, y] = local(e), dx = x - p.x, dy = y - p.y;
      if (P.size === 1) this._unDedo(p, dx, dy, e);
      p.x = x; p.y = y;
      if (P.size >= 2) this._dosDedos();
    });
    const fin = e => {
      const p = P.get(e.pointerId); if (!p) return;
      P.delete(e.pointerId);
      const [x, y] = local(e), quieto = Math.hypot(x - p.x0, y - p.y0) < 8, breve = performance.now() - p.t < 350;
      if (P.size === 0) {
        this.o.alInteractuar?.(false);
        if (quieto && breve && e.type === 'pointerup' && !this._multi) {
          const ahora = performance.now(), doble = ahora - this._ultimoToque < 320 && Math.hypot(x - this._ultimoXY[0], y - this._ultimoXY[1]) < 30;
          this._ultimoToque = doble ? 0 : ahora; this._ultimoXY = [x, y];
          if (doble) { const q = this.o.puntoEn?.(x, y); if (q) this.fijarPivote(q); }
          else this.o.alTocar?.(x, y, false);
        }
        this._multi = false;
      } else this._iniciarGesto();
    };
    el.addEventListener('pointerup', fin); el.addEventListener('pointercancel', fin);
    el.addEventListener('wheel', e => {
      e.preventDefault(); if (this.bloqueada) return;
      const [x, y] = local(e);
      const ahora = performance.now();
      if (!this._anclaRueda || ahora - this._tRueda > 400 || Math.hypot(x - this._xyRueda[0], y - this._xyRueda[1]) > 12) {
        this.recordar(); this._anclaRueda = this.o.puntoEn?.(x, y) || this._enPlano(x, y); this._xyRueda = [x, y];
      }
      this._tRueda = ahora;
      this.zoom(Math.exp(e.deltaY * 0.0012 * this.sens), this._anclaRueda);
    }, {passive: false});
  }
  _iniciarGesto() {
    const P = [...this._punteros.values()];
    if (P.length >= 2) {
      this._multi = true;
      const cx = (P[0].x + P[1].x) / 2, cy = (P[0].y + P[1].y) / 2;
      const q = this.o.puntoEn?.(cx, cy) || this._enPlano(cx, cy);
      this._ancla = {punto: q, prof: this._profundidad(q), d: Math.hypot(P[0].x - P[1].x, P[0].y - P[1].y), cx, cy,
                     ang: Math.atan2(P[1].y - P[0].y, P[1].x - P[0].x)};
    } else if (P.length === 1) {
      const p = P[0], necesita = this.modo === 'panear' || this.modo === 'zoom' || p.boton === 2 || p.boton === 1;
      const q = necesita ? (this.o.puntoEn?.(p.x, p.y) || this._enPlano(p.x, p.y)) : null;
      this._ancla = {punto: q, prof: q ? this._profundidad(q) : this.distancia()};
    }
  }
  _unDedo(p, dx, dy, e) {
    const k = 0.0055 * this.sens;
    const modo = p.boton === 2 ? 'panear' : p.boton === 1 ? 'zoom' : (e.shiftKey ? 'panear' : this.modo);
    if (modo === 'orbitar') this.girar(-dx * k, dy * k, false);
    else if (modo === 'caminar') this.girar(dx * k * 0.6, -dy * k * 0.6, true);
    else if (modo === 'panear') this.panearPx(dx * this.sens, dy * this.sens, this._ancla?.prof);
    else if (modo === 'zoom') this.zoom(Math.exp(dy * 0.006 * this.sens), this._ancla?.punto || this.mira);
  }
  _dosDedos() {
    const P = [...this._punteros.values()], a = this._ancla; if (!a || P.length < 2) return;
    const cx = (P[0].x + P[1].x) / 2, cy = (P[0].y + P[1].y) / 2, d = Math.hypot(P[0].x - P[1].x, P[0].y - P[1].y);
    if (a.d > 0 && d > 0) this.zoom(Math.pow(a.d / d, this.sens), a.punto);
    a.prof = this._profundidad(a.punto);
    this.panearPx(cx - a.cx, cy - a.cy, a.prof);
    a.d = d; a.cx = cx; a.cy = cy;
  }
  _profundidad(q) {
    return Math.max(0.05, v1.copy(q).sub(this.camera.position).dot(this.camera.getWorldDirection(v2)));
  }
  /** Punto del plano perpendicular a la vista que pasa por la mira, bajo el píxel (x, y). */
  _enPlano(x, y) {
    const cam = this.camera, ndc = new THREE.Vector3(x / this.dom.clientWidth * 2 - 1, -(y / this.dom.clientHeight) * 2 + 1, 0.5).unproject(cam);
    const dir = ndc.sub(cam.position).normalize(), n = cam.getWorldDirection(v2);
    const t = v1.copy(this.mira).sub(cam.position).dot(n) / Math.max(1e-6, dir.dot(n));
    return cam.position.clone().addScaledVector(dir, Math.max(0.1, t));
  }
}
