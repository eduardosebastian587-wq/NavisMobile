// Visor WebGL: render bajo demanda, resolución dinámica y selección/profundidad por GPU (sin raycast).
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

const PROF_VS = `#include <clipping_planes_pars_vertex>
void main(){ vec4 mvPosition = modelViewMatrix * vec4(position,1.0); gl_Position = projectionMatrix * mvPosition;
#include <clipping_planes_vertex>
}`;
const PROF_FS = `#include <clipping_planes_pars_fragment>
void main(){
#include <clipping_planes_fragment>
  vec4 enc = fract(gl_FragCoord.z * vec4(1.0, 255.0, 65025.0, 16581375.0));
  enc -= enc.yzww * vec4(1.0/255.0, 1.0/255.0, 1.0/255.0, 0.0);
  gl_FragColor = enc;
}`;

export class Visor {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    this.renderer.localClippingEnabled = true;
    this.renderer.setClearColor(0x1b1e24, 1);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
    this.camera.layers.enable(1);               // capa 1 = ayudantes (se excluyen en las pasadas de selección)
    this.ayudantes = new THREE.Group(); this.ayudantes.traverse?.(() => {}); this.scene.add(this.ayudantes);
    this.raiz = null; this.mallas = []; this.caja = new THREE.Box3(new THREE.Vector3(-50, 0, -50), new THREE.Vector3(50, 30, 50));

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x555566, 0.6));
    this.sol = new THREE.DirectionalLight(0xffffff, 1.2); this.sol.position.set(300, 800, 400); this.scene.add(this.sol);
    const pm = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; pm.dispose();

    this.draco = new DRACOLoader().setDecoderPath(import.meta.env.BASE_URL + 'draco/');
    this.gltf = new GLTFLoader().setDRACOLoader(this.draco);

    this.rtProf = new THREE.WebGLRenderTarget(1, 1, { depthBuffer: true });
    this.matProf = new THREE.ShaderMaterial({ vertexShader: PROF_VS, fragmentShader: PROF_FS, clipping: true, side: THREE.DoubleSide });
    this._buf = new Uint8Array(4);

    this._sucio = true; this._interactuando = false; this._frames = 0; this._t0 = performance.now(); this.fps = 0;
    this.alCuadro = null;                       // (dt) => boolean: true si hubo cambios
    new ResizeObserver(() => this._redimensionar()).observe(canvas.parentElement);
    this._redimensionar();
    let ult = performance.now();
    const bucle = (t) => {
      const dt = Math.min(0.1, (t - ult) / 1000); ult = t;
      if (this.alCuadro?.(dt)) this._sucio = true;
      if (this._sucio) { this._sucio = false; this._dibujar(); }
      requestAnimationFrame(bucle);
    };
    requestAnimationFrame(bucle);
  }
  invalidar() { this._sucio = true; }
  interactuando(a) {
    this._interactuando = a;
    this.renderer.setPixelRatio(a ? 1 : Math.min(window.devicePixelRatio || 1, 2));
    this._redimensionar();
  }
  _redimensionar() {
    const p = this.canvas.parentElement, w = Math.max(1, p.clientWidth), h = Math.max(1, p.clientHeight);
    this.renderer.setSize(w, h, false); this.canvas.style.width = w + 'px'; this.canvas.style.height = h + 'px';
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); this._sucio = true;
  }
  _dibujar() {
    this.renderer.render(this.scene, this.camera);
    this._frames++; const t = performance.now();
    if (t - this._t0 > 1000) { this.fps = Math.round(this._frames * 1000 / (t - this._t0)); this._frames = 0; this._t0 = t; }
  }
  fijarSol(dir, energia = 3) {
    this.sol.position.copy(new THREE.Vector3().fromArray(dir).normalize().multiplyScalar(1000));
    this.sol.intensity = THREE.MathUtils.clamp(energia / 2, 0.5, 3); this._sucio = true;
  }
  corte(plano) { this.renderer.clippingPlanes = plano ? [plano] : []; this._sucio = true; }

  // ---------------------------------------------------------------- carga
  async cargar(buffer) {
    this.quitar();
    const gltf = await new Promise((ok, no) => this.gltf.parse(buffer, '', ok, no));
    this.raiz = gltf.scene; this.scene.add(this.raiz);
    this.actualizarMallas();
    this.caja = new THREE.Box3().setFromObject(this.raiz);
    return this.raiz;
  }
  /** Añade una capa extra (otro GLB) al mismo modelo. */
  async agregar(buffer) {
    const g = await new Promise((ok, no) => this.gltf.parse(buffer, '', ok, no));
    this.raiz.add(g.scene); this.actualizarMallas(); return g.scene;
  }
  quitar() {
    if (!this.raiz) return;
    this.scene.remove(this.raiz);
    this.raiz.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); [].concat(o.material).forEach((m) => m.dispose()); } });
    this.raiz = null; this.mallas = []; this._sucio = true;
  }
  actualizarMallas() {
    this.mallas = [];
    this.raiz.traverse((o) => {
      if (!o.isMesh) return;
      o.userData.idx = this.mallas.length; this.mallas.push(o);
      const g = o.geometry; o.userData.tris = Math.round((g.index ? g.index.count : g.attributes.position.count) / 3);
      const c = new THREE.Color().setRGB((((this.mallas.length) >> 16) & 255) / 255, (((this.mallas.length) >> 8) & 255) / 255, ((this.mallas.length) & 255) / 255, THREE.LinearSRGBColorSpace);
      o.userData.idMat = new THREE.MeshBasicMaterial({ color: c, toneMapped: false, side: THREE.DoubleSide });
    });
  }
  triangulos() { let n = 0; for (const m of this.mallas) if (m.visible) n += m.userData.tris; return n; }

  // ---------------------------------------------------------------- pasadas de 1 píxel
  _pasada(x, y, fn) {
    const r = this.renderer, cam = this.camera, w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    const prevRT = r.getRenderTarget(), prevPR = r.getPixelRatio(), prevCol = new THREE.Color(); r.getClearColor(prevCol);
    const prevA = r.getClearAlpha();
    cam.layers.disable(1); cam.setViewOffset(w, h, Math.floor(x), Math.floor(y), 1, 1);
    r.setRenderTarget(this.rtProf); fn(); r.readRenderTargetPixels(this.rtProf, 0, 0, 1, 1, this._buf);
    r.setRenderTarget(prevRT); cam.clearViewOffset(); cam.layers.enable(1); r.setClearColor(prevCol, prevA);
    return this._buf;
  }
  /** Punto del mundo bajo el píxel (x, y) del lienzo, o null si no hay geometría. */
  puntoEn(x, y) {
    if (!this.raiz) return null;
    const b = this._pasada(x, y, () => {
      this.renderer.setClearColor(0xffffff, 1); this.scene.overrideMaterial = this.matProf;
      this.renderer.clear(); this.renderer.render(this.scene, this.camera); this.scene.overrideMaterial = null;
    });
    const z = b[0] / 255 + b[1] / 65025 + b[2] / 16581375 + b[3] / 4228250625;
    if (z >= 0.99999) return null;
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    return new THREE.Vector3((x / w) * 2 - 1, -(y / h) * 2 + 1, z * 2 - 1).unproject(this.camera);
  }
  /** Malla visible bajo el píxel (x, y), o null. */
  mallaEn(x, y) {
    if (!this.raiz) return null;
    const orig = new Map();
    for (const m of this.mallas) { orig.set(m, m.material); m.material = m.userData.idMat; }
    const b = this._pasada(x, y, () => {
      this.renderer.setClearColor(0x000000, 1); this.renderer.clear(); this.renderer.render(this.scene, this.camera);
    });
    for (const [m, mat] of orig) m.material = mat;
    const id = (b[0] << 16) | (b[1] << 8) | b[2];
    return id > 0 ? this.mallas[id - 1] || null : null;
  }
}
