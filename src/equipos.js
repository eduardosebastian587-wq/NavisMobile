// Equipos animados del Área 1313 (equipos-1313-v1) y animaciones.json. Montaje según plantilla_visor_1313.html.
import * as THREE from 'three';

const PBR = { acero: [0.35, 0.6], default: [0.2, 0.7] };

export class Equipos {
  constructor(json, buf) {
    this.grupo = new THREE.Group(); this.grupo.name = 'equipos';
    this.marco = new THREE.Group(); this.marco.rotation.y = Math.PI; this.marco.position.set(json.TX || 0, json.TZ || 0, -(json.TY || 0));
    this.grupo.add(this.marco);
    this.nodos = new Map(); this.estirables = new Map(); this.rest = new Map();
    const por = new Map(json.partes.map((p) => [p.id, p]));
    const piv = (p) => p.pivote || (p.padre && por.get(p.padre) ? piv(por.get(p.padre)) : [0, 0, 0]);
    const crear = (p) => {
      if (this.nodos.has(p.id)) return this.nodos.get(p.id);
      const padreP = p.padre ? por.get(p.padre) : null, padre = padreP ? crear(padreP) : this.marco;
      const pv = piv(p), pp = padreP ? piv(padreP) : [0, 0, 0];
      const g = new THREE.Group(); g.name = p.id; g.position.set(pv[0] - pp[0], pv[1] - pp[1], pv[2] - pp[2]);
      padre.add(g); this.nodos.set(p.id, g); this.rest.set(p.id, g.position.clone());
      for (const m of p.mallas || []) {
        if (!m.vert) continue;
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(buf.slice(m.pos, m.pos + m.vert * 12)), 3));
        geo.setAttribute('normal', new THREE.BufferAttribute(new Int8Array(buf.slice(m.nor, m.nor + m.vert * 3)), 3, true));
        const [met, rug] = PBR[m.disciplina] || PBR.default;
        const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: m.color, metalness: met, roughness: rug, side: THREE.DoubleSide }));
        mesh.name = `${p.id}:${m.disciplina || ''}`;
        if (p.estirable) {      // cuelga del contenedor del padre; se estira al animar
          mesh.position.set(-pp[0], -pp[1], -pp[2]); mesh.frustumCulled = false; padre.add(mesh);
          const e = this.estirables.get(p.id) || { malla: [], y1: p.estirable.y1, y2: p.estirable.y2 };
          e.malla.push({ geo, pos0: geo.attributes.position.array.slice() }); this.estirables.set(p.id, e);
        } else { mesh.position.set(-pv[0], -pv[1], -pv[2]); g.add(mesh); }
      }
      return g;
    };
    json.partes.forEach(crear);
    this.anims = []; this.ignoradas = 0;
  }
  /** Sustituye todos los materiales por los del tema (opcional) — no usado por defecto. */
  cargarAnimaciones(json) { this.anims = json.animaciones || []; }

  _valor(pista, t) {
    const k = pista.claves; if (!k.length) return [0, 0, 0];
    if (t <= k[0][0]) return k[0][1]; if (t >= k[k.length - 1][0]) return k[k.length - 1][1];
    let i = 0; while (k[i + 1][0] < t) i++;
    const [t0, a] = k[i], [t1, b] = k[i + 1]; let u = (t - t0) / (t1 - t0 || 1);
    const modo = pista.interpolacion || 'suave';
    if (modo === 'escalon') u = 0; else if (modo !== 'lineal') u = u * u * (3 - 2 * u);
    return a.map((v, j) => v + (b[j] - v) * u);
  }
  /** Tiempo efectivo según el modo de bucle. */
  tiempo(anim, t) {
    const d = anim.duracion || 1;
    if (anim.bucle === 'bucle') return ((t % d) + d) % d;
    if (anim.bucle === 'vaiven') { const c = ((t % (2 * d)) + 2 * d) % (2 * d); return c <= d ? c : 2 * d - c; }
    return Math.min(Math.max(t, 0), d);
  }
  /** Aplica la animación en el instante t (segundos). */
  aplicar(anim, t) {
    t = this.tiempo(anim, t);
    for (const [id, g] of this.nodos) { g.position.copy(this.rest.get(id)); g.rotation.set(0, 0, 0); }
    const dy = new Map(); this.ignoradas = 0;
    for (const p of anim.pistas) {
      const g = this.nodos.get(p.objetivo); if (!g) { this.ignoradas++; continue; }
      const v = this._valor(p, t);
      if (p.propiedad === 'posicion') { if (this.estirables.has(p.objetivo)) dy.set(p.objetivo, v[1]); else g.position.add(new THREE.Vector3(...v)); }
      else if (p.propiedad === 'rotacion') g.rotation.set(...v.map(THREE.MathUtils.degToRad), 'XYZ');
      else this.ignoradas++;
    }
    for (const [id, e] of this.estirables) {
      const d = dy.get(id) || 0;
      for (const m of e.malla) {
        const a = m.geo.attributes.position.array, o = m.pos0;
        for (let i = 0; i < a.length; i += 3) { const y = o[i + 1]; a[i + 1] = y + d * (y <= e.y1 ? 1 : y >= e.y2 ? 0 : (e.y2 - y) / (e.y2 - e.y1)); }
        m.geo.attributes.position.needsUpdate = true; m.geo.computeBoundingSphere();
      }
    }
    return true;
  }
}
