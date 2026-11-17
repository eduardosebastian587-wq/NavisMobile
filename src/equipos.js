// Equipos animados del Área 1313: monta la jerarquía (pórtico, carros, ganchos, plumas, molinos) y aplica animaciones.
import * as THREE from 'three';

/** Monta los equipos. json = equipos-1313-v1, buf = ArrayBuffer del .bin. */
export function montarEquipos(json, buf) {
  const marco = new THREE.Group(); marco.name = 'equipos';
  marco.rotation.y = Math.PI; marco.position.set(json.TX, json.TZ, -json.TY);
  const nodos = new Map(), partes = new Map(), mallas = [];
  for (const p of json.partes) partes.set(p.id, p);
  const pivoteDe = p => p.pivote || (p.padre && partes.get(p.padre) && pivoteDe(partes.get(p.padre))) || [0, 0, 0];
  const raices = [];
  // 1) un grupo por parte
  for (const p of json.partes) {
    const g = new THREE.Group(); g.name = p.id; g.userData.parte = p;
    nodos.set(p.id, g);
  }
  for (const p of json.partes) nodos.get(p.id).userData.pivote = new THREE.Vector3().fromArray(pivoteDe(p));
  // 2) jerarquía y posiciones relativas al pivote del padre
  for (const p of json.partes) {
    const g = nodos.get(p.id), piv = g.userData.pivote;
    const padre = p.padre && nodos.get(p.padre);
    if (padre) { g.position.copy(piv).sub(padre.userData.pivote); padre.add(g); } else { g.position.copy(piv); marco.add(g); raices.push(g); }
    g.userData.rest = g.position.clone();
  }
  // 3) mallas
  for (const p of json.partes) {
    const g = nodos.get(p.id);
    for (const m of p.mallas || []) {
      if (!m.vert) continue;
      const pos = new Float32Array(buf, m.pos, m.vert * 3);
      const nor = new Int8Array(buf, m.nor, m.vert * 3);
      const nf = new Float32Array(m.vert * 3);
      for (let i = 0; i < nf.length; i++) nf[i] = Math.max(-1, nor[i] / 127);
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
      geo.setAttribute('normal', new THREE.BufferAttribute(nf, 3));
      const mat = new THREE.MeshStandardMaterial({color: m.color, metalness: m.disciplina === 'Mechanical' ? 0.5 : 0.2, roughness: 0.55, side: THREE.DoubleSide});
      const malla = new THREE.Mesh(geo, mat); malla.name = `${p.id} (${m.disciplina || 'equipo'})`;
      malla.userData.color = mat.color.clone(); malla.userData.equipo = p.id;
      if (p.estirable) {
        // gancho + cable: el nodo cuelga del padre en su origen; la malla va desplazada −pivote del padre
        const pp = p.padre && nodos.get(p.padre), off = pp ? pp.userData.pivote : new THREE.Vector3();
        malla.position.set(-off.x, -off.y, -off.z);
        g.position.set(0, 0, 0); g.userData.rest.set(0, 0, 0);
        malla.userData.pos0 = geo.attributes.position.array.slice(); malla.frustumCulled = false;
        g.userData.estirable = {malla, y1: p.estirable.y1, y2: p.estirable.y2};
      } else { malla.position.copy(g.userData.pivote).multiplyScalar(-1); }
      g.add(malla); mallas.push(malla);
    }
  }
  marco.updateMatrixWorld(true);
  for (const m of mallas) { m.matrixAutoUpdate = false; m.updateMatrix(); }
  return {grupo: marco, nodos, mallas};
}

function interpolar(claves, t, modo) {
  if (t <= claves[0][0]) return claves[0][1];
  const n = claves.length;
  if (t >= claves[n - 1][0]) return claves[n - 1][1];
  let i = 0; while (i < n - 2 && t > claves[i + 1][0]) i++;
  const [t0, a] = claves[i], [t1, b] = claves[i + 1];
  if (modo === 'escalon') return a;
  let u = (t - t0) / (t1 - t0 || 1);
  if (modo === 'suave' || modo === 'curva' || !modo) u = u * u * (3 - 2 * u);
  return a.map((v, k) => v + (b[k] - v) * u);
}

/** Reproductor de animaciones sobre los nodos de equipos. */
export class Animador {
  constructor(nodos, animaciones, alCambiar) {
    this.nodos = nodos; this.lista = animaciones; this.alCambiar = alCambiar;
    this.actual = null; this.t = 0; this.reproduciendo = false; this.bucle = null; this.velocidad = 1;
  }
  elegir(id) { this.actual = this.lista.find(a => a.id === id) || null; this.t = 0; this.aplicar(0); }
  duracion() { return this.actual?.duracion || 0; }
  /** Pistas que sí se pueden aplicar con los datos disponibles. */
  pistasValidas(a = this.actual) { return (a?.pistas || []).filter(p => this.nodos.has(p.objetivo)); }
  ignoradas(a = this.actual) { return (a?.pistas || []).filter(p => !this.nodos.has(p.objetivo)).map(p => p.objetivo + '.' + p.propiedad); }
  restablecer() { for (const g of this.nodos.values()) { g.position.copy(g.userData.rest); g.rotation.set(0, 0, 0); this._estirar(g, 0); } }
  _estirar(g, dy) {
    const e = g.userData.estirable; if (!e) return;
    const p0 = e.malla.userData.pos0, p = e.malla.geometry.attributes.position.array, {y1, y2} = e;
    for (let i = 0; i < p0.length; i += 3) { const y = p0[i + 1]; p[i + 1] = y + dy * (y <= y1 ? 1 : y >= y2 ? 0 : (y2 - y) / (y2 - y1)); }
    e.malla.geometry.attributes.position.needsUpdate = true;
  }
  /** Aplica el tiempo t (s) de la animación actual. */
  aplicar(t) {
    const a = this.actual; if (!a) return;
    this.restablecer();
    const dur = a.duracion || 1;
    let tt = t;
    if (a.bucle === 'bucle') tt = ((t % dur) + dur) % dur;
    else if (a.bucle === 'vaiven') { const m = ((t % (2 * dur)) + 2 * dur) % (2 * dur); tt = m > dur ? 2 * dur - m : m; }
    else tt = Math.min(Math.max(t, 0), dur);
    for (const p of this.pistasValidas(a)) {
      const g = this.nodos.get(p.objetivo), v = interpolar(p.claves, tt, p.interpolacion);
      if (p.propiedad === 'posicion') {
        if (g.userData.estirable) this._estirar(g, v[1]);
        g.position.x += v[0]; g.position.y += g.userData.estirable ? 0 : v[1]; g.position.z += v[2];
      } else if (p.propiedad === 'rotacion') g.rotation.set(THREE.MathUtils.degToRad(v[0]), THREE.MathUtils.degToRad(v[1]), THREE.MathUtils.degToRad(v[2]), 'XYZ');
    }
    this.alCambiar?.();
  }
  /** Para el recorrido: aplica la animación en un tiempo absoluto. */
  alTiempo(t) { if (this.actual) this.aplicar(t); }
  tick(dt) {
    if (!this.reproduciendo || !this.actual) return false;
    this.t += dt * this.velocidad; const dur = this.actual.duracion;
    if (this.actual.bucle !== 'bucle' && this.actual.bucle !== 'vaiven' && this.t >= dur) { this.t = dur; this.reproduciendo = false; this.alFin?.(); }
    this.aplicar(this.t); this.alFrame?.(); return true;
  }
}
