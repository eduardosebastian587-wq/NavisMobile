// Reproductor de recorridos de cámara (formato recorrido-hito-v1).
export class Recorrido {
  /** @param datos JSON del recorrido  @param nav Navegacion  @param o {alCuadro(t_s), alFin()} */
  constructor(datos, nav, o = {}) {
    this.d = datos; this.nav = nav; this.o = o;
    this.fps = datos.fps || 30; this.tray = datos.trayectoria_three;
    this.duracion = (this.tray.length - 1) / this.fps;
    this.desfase = datos.desfase_ciclo_s || 0;
    this.t = 0; this.velocidad = 1; this.reproduciendo = false; this.nombre = datos.nombre || '';
  }
  poner(t) {
    this.t = Math.min(Math.max(0, t), this.duracion);
    const f = this.t * this.fps, i = Math.min(this.tray.length - 2, Math.floor(f)), u = f - i, a = this.tray[i], b = this.tray[i + 1];
    const L = k => a[k] + (b[k] - a[k]) * u;
    this.nav.camera.position.set(L(0), L(1), L(2)); this.nav.mira.set(L(3), L(4), L(5));
    this.nav._listo(false);
    this.o.alCuadro?.(this.t - this.desfase);
  }
  reproducir() { if (this.t >= this.duracion) this.t = 0; this.nav.recordar(); this.reproduciendo = true; this.nav.bloqueada = true; this.poner(this.t); }
  pausar() { this.reproduciendo = false; this.nav.bloqueada = false; if (this.nav.modo === 'caminar') this.nav.fijarModo('caminar'); }
  detener() { this.pausar(); }
  tick(dt) {
    if (!this.reproduciendo) return false;
    this.t += dt * this.velocidad;
    if (this.t >= this.duracion) { this.poner(this.duracion); this.pausar(); this.o.alFin?.(); return true; }
    this.poner(this.t); return true;
  }
}
