// Reproductor de recorridos (formato recorrido-hito-v1): interpolación lineal de posición y punto de mira.
import * as THREE from 'three';

export class Recorrido {
  constructor(json, nav) {
    this.nav = nav; this.fps = json.fps || 30; this.tr = json.trayectoria_three;
    this.duracion = (this.tr.length - 1) / this.fps; this.desfase = json.desfase_ciclo_s || 0;
    this.t = 0; this.velocidad = 1; this.reproduciendo = false;
  }
  /** Tiempo del ciclo de equipos para este instante. */
  get tCiclo() { return this.t - this.desfase; }
  reproducir() { if (this.t >= this.duracion) this.t = 0; this.reproduciendo = true; this.nav.bloqueada = true; }
  pausar() { this.reproduciendo = false; }
  detener() { this.reproduciendo = false; this.nav.bloqueada = false; }
  ir(t) { this.t = THREE.MathUtils.clamp(t, 0, this.duracion); this._aplicar(); }
  /** Avanza dt segundos; devuelve true si cambió algo. */
  actualizar(dt) {
    if (!this.reproduciendo) return false;
    this.t += dt * this.velocidad;
    if (this.t >= this.duracion) { this.t = this.duracion; this.reproduciendo = false; }
    this._aplicar(); return true;
  }
  _aplicar() {
    const f = this.t * this.fps, i = Math.min(this.tr.length - 2, Math.floor(f)), u = f - i, a = this.tr[i], b = this.tr[i + 1];
    const L = (k) => a[k] + (b[k] - a[k]) * u;
    this.nav.camera.position.set(L(0), L(1), L(2)); this.nav.mira.set(L(3), L(4), L(5));
    this.nav._listo(true);
  }
}
