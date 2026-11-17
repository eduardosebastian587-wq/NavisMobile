// Correas transportadoras: cintas finas con franjas que avanzan sobre la línea central de cada tramo.
import * as THREE from 'three';

function texturaFranjas() {
  const c = document.createElement('canvas'); c.width = 64; c.height = 16;
  const g = c.getContext('2d'); g.fillStyle = '#2b2f36'; g.fillRect(0, 0, 64, 16);
  g.fillStyle = '#f0b030'; g.fillRect(0, 0, 14, 16);
  const t = new THREE.CanvasTexture(c); t.wrapS = THREE.RepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping; t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Correas {
  constructor(datos, ayudas) {
    this.grupo = new THREE.Group(); this.grupo.name = 'correas'; this.grupo.layers.set(1);
    this.texturas = []; this.velocidad = 3; this.activa = false; this.largoFranja = 1.2;
    for (const c of datos.correas || []) for (const t of c.tramos || []) this._tramo(c, t);
    this.grupo.visible = false; ayudas.add(this.grupo);
  }
  _tramo(c, t) {
    // ejes de Blender (x, y, z) → Three (x, z, −y)
    const P = (t.puntos || []).map(p => new THREE.Vector3(p[0], p[2], -p[1]));
    if (P.length < 2) return;
    const ancho = t.ancho_m || 1, pos = [], uv = [], idx = [];
    let acc = 0; const arriba = new THREE.Vector3(0, 1, 0);
    for (let i = 0; i < P.length; i++) {
      if (i) acc += P[i].distanceTo(P[i - 1]);
      const d = (i < P.length - 1 ? P[i + 1].clone().sub(P[i]) : P[i].clone().sub(P[i - 1])).normalize();
      const lado = new THREE.Vector3().crossVectors(d, arriba); if (lado.lengthSq() < 1e-6) lado.set(1, 0, 0); lado.normalize().multiplyScalar(ancho / 2);
      const a = P[i].clone().add(lado).addScaledVector(arriba, 0.03), b = P[i].clone().sub(lado).addScaledVector(arriba, 0.03);
      pos.push(a.x, a.y, a.z, b.x, b.y, b.z); uv.push(acc / this.largoFranja, 0, acc / this.largoFranja, 1);
      if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setIndex(idx);
    const tex = texturaFranjas(); this.texturas.push(tex);
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({map: tex, side: THREE.DoubleSide, toneMapped: false}));
    m.layers.set(1); m.name = `${c.tag} (${t.tipo})`; m.frustumCulled = false; this.grupo.add(m);
  }
  mostrar(v) { this.activa = v; this.grupo.visible = v; }
  tick(dt) {
    if (!this.activa) return false;
    for (const t of this.texturas) t.offset.x -= this.velocidad * dt / this.largoFranja;
    return true;
  }
  liberar() { this.grupo.removeFromParent(); this.grupo.traverse(n => { n.geometry?.dispose(); n.material?.dispose(); }); this.texturas.forEach(t => t.dispose()); }
}
