// Correas transportadoras: cinta fina sobre la línea central, con franjas que avanzan (hito_correas.json).
import * as THREE from 'three';

const VEL = 3; // m/s
function textura() {
  const c = document.createElement('canvas'); c.width = 4; c.height = 32;
  const g = c.getContext('2d'); g.fillStyle = '#2d3138'; g.fillRect(0, 0, 4, 32); g.fillStyle = '#f2c230'; g.fillRect(0, 0, 4, 12);
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Correas {
  constructor(json) {
    this.grupo = new THREE.Group(); this.grupo.name = 'correas'; this.mats = []; this.activa = true;
    this.porTag = [];
    for (const cor of json.correas) {
      const g = new THREE.Group(); g.name = cor.tag; g.userData = { tag: cor.tag, sentido: cor.sentido_carga };
      for (const tr of cor.tramos) this._tramo(tr, g);
      this.grupo.add(g); this.porTag.push(g);
    }
    this.grupo.traverse((o) => o.layers.set(1));
  }
  _tramo(tr, padre) {
    // ejes Blender (x, y, z) → Three (x, z, -y)
    const P = tr.puntos.map(([x, y, z]) => new THREE.Vector3(x, z, -y)), w = tr.ancho_m || 1;
    const pos = [], uv = [], idx = []; let acc = 0;
    for (let i = 0; i < P.length; i++) {
      const prev = P[Math.max(0, i - 1)], next = P[Math.min(P.length - 1, i + 1)];
      const dir = next.clone().sub(prev).normalize();
      const lado = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize().multiplyScalar(w / 2);
      if (i) acc += P[i].distanceTo(P[i - 1]);
      const c = P[i].clone().add(new THREE.Vector3(0, 0.03, 0));
      pos.push(c.x - lado.x, c.y, c.z - lado.z, c.x + lado.x, c.y, c.z + lado.z); uv.push(0, acc, 1, acc);
      if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    g.setIndex(idx); g.computeVertexNormals();
    const tex = textura(); tex.repeat.set(1, 1 / 1.0); // 1 franja por metro
    const m = new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide });
    m.userData.retorno = tr.tipo === 'retorno'; this.mats.push(m);
    const mesh = new THREE.Mesh(g, m); mesh.frustumCulled = false; padre.add(mesh);
  }
  /** Avanza las franjas; devuelve true si hubo movimiento. */
  actualizar(dt) {
    if (!this.activa) return false;
    for (const m of this.mats) m.map.offset.y -= VEL * dt;
    return true;
  }
  visible(v) { this.activa = v; this.grupo.visible = v; }
}
