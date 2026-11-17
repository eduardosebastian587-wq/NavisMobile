// Visor: escena Three.js, render bajo demanda, carga de GLB y selección por GPU (sin raycast).
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {DRACOLoader} from 'three/examples/jsm/loaders/DRACOLoader.js';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';

const CAPA_AYUDA = 1;   // marcas de pivote, medidas y cintas de correa: no participan en la selección

const VS = `#include <clipping_planes_pars_vertex>
void main(){ #include <begin_vertex>
 #include <project_vertex>
 #include <clipping_planes_vertex> }`;
const FS_PROF = `#include <clipping_planes_pars_fragment>
void main(){ #include <clipping_planes_fragment>
 vec4 enc = fract(gl_FragCoord.z * vec4(1.0, 255.0, 65025.0, 16581375.0));
 enc -= enc.yzww * vec4(1.0/255.0, 1.0/255.0, 1.0/255.0, 0.0);
 gl_FragColor = enc; }`;
const FS_ID = `#include <clipping_planes_pars_fragment>
uniform vec3 color;
void main(){ #include <clipping_planes_fragment>
 gl_FragColor = vec4(color, 1.0); }`;

export class Visor {
  constructor(canvas, o = {}) {
    this.canvas = canvas; this.o = o;
    const r = this.renderer = new THREE.WebGLRenderer({canvas, antialias: true, powerPreference: 'high-performance', preserveDrawingBuffer: !!o.conservar});
    r.localClippingEnabled = true; r.clippingPlanes = [];
    r.toneMapping = THREE.NeutralToneMapping; r.toneMappingExposure = 0.8;
    this.escena = new THREE.Scene(); this.escena.background = new THREE.Color(0x9fb4c8);
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000); this.camera.position.set(60, 50, 60);
    this.camera.layers.enable(CAPA_AYUDA);
    this.hemi = new THREE.HemisphereLight(0xdfe9ff, 0x6b5f50, 0.6); this.escena.add(this.hemi);
    this.sol = new THREE.DirectionalLight(0xffffff, 2.2); this.sol.position.set(0.44, 0.64, 0.63).multiplyScalar(1000); this.escena.add(this.sol);
    const pm = new THREE.PMREMGenerator(r);
    this.escena.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; this.escena.environmentIntensity = 0.5; pm.dispose();
    this.raiz = new THREE.Group(); this.escena.add(this.raiz);
    this.ayudas = new THREE.Group(); this.escena.add(this.ayudas);
    this.mallas = []; this.capasExtra = new Map();
    this.caja = new THREE.Box3(new THREE.Vector3(-1, -1, -1), new THREE.Vector3(1, 1, 1));
    this.triangulos = 0; this.sucio = true; this.interactuando = false; this._ultimoPR = 0;
    this.ticks = []; this.fps = 0; this._f = {n: 0, t: performance.now()};
    this.plano = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);

    const dr = new DRACOLoader(); dr.setDecoderPath('./draco/'); dr.setDecoderConfig({type: 'wasm'});
    this.loader = new GLTFLoader().setDRACOLoader(dr);

    this.rt = new THREE.WebGLRenderTarget(1, 1, {type: THREE.UnsignedByteType, format: THREE.RGBAFormat, depthBuffer: true,
      minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, generateMipmaps: false});
    this.matProf = new THREE.ShaderMaterial({vertexShader: VS, fragmentShader: FS_PROF, clipping: true, side: THREE.DoubleSide});
    this._buf = new Uint8Array(4);

    new ResizeObserver(() => this.ajustar()).observe(canvas.parentElement || canvas);
    this.ajustar(); this._bucle = this._bucle.bind(this); requestAnimationFrame(this._bucle);
  }

  // ------------------------------------------------------------- render
  pedir() { this.sucio = true; }
  ajustar() {
    const el = this.canvas.parentElement || this.canvas, w = Math.max(2, el.clientWidth), h = Math.max(2, el.clientHeight);
    this._aplicarPR(true); this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); this.pedir();
  }
  _aplicarPR(forzar = false) {
    const pr = this.interactuando ? 1 : Math.min(window.devicePixelRatio || 1, 2);
    if (pr !== this._ultimoPR || forzar) { this._ultimoPR = pr; this.renderer.setPixelRatio(pr); const el = this.canvas.parentElement || this.canvas; this.renderer.setSize(Math.max(2, el.clientWidth), Math.max(2, el.clientHeight), false); this.pedir(); }
  }
  interactuar(activo) { this.interactuando = activo; this._aplicarPR(); }
  _bucle(t) {
    requestAnimationFrame(this._bucle);
    const dt = Math.min(0.1, (t - (this._t || t)) / 1000); this._t = t;
    for (const f of this.ticks) if (f(dt)) this.sucio = true;
    if (!this.sucio) return;
    this.sucio = false; this.renderer.render(this.escena, this.camera);
    const f = this._f; f.n++; if (t - f.t > 700) { this.fps = Math.round(f.n * 1000 / (t - f.t)); f.n = 0; f.t = t; }
  }

  // ------------------------------------------------------------- escena
  configurarEscena(esc) {
    if (!esc) return;
    const s = esc.soles?.[0];
    if (s?.hacia_sol_three) { this.sol.position.fromArray(s.hacia_sol_three).normalize().multiplyScalar(1000); this.sol.intensity = 1.6 + 0.2 * (s.energia || 3); }
    if (esc.camara?.lente_mm) {
      const sensor = esc.camara.sensor_mm || 36;
      this.camera.fov = THREE.MathUtils.radToDeg(2 * Math.atan(sensor / 2 / esc.camara.lente_mm / Math.max(1, this.camera.aspect)) );
      this.camera.fov = THREE.MathUtils.clamp(this.camera.fov, 30, 70); this.camera.updateProjectionMatrix();
    }
    this.pedir();
  }

  /** Carga un GLB (ArrayBuffer). Devuelve {grupo, mallas}. */
  cargarGLB(buf) {
    return new Promise((ok, err) => this.loader.parse(buf, '', gltf => {
      const mallas = [];
      gltf.scene.traverse(n => { if (n.isMesh) mallas.push(n); });
      gltf.scene.updateMatrixWorld(true);
      for (const m of mallas) {
        m.matrixAutoUpdate = false; m.userData.color = (m.material?.color || new THREE.Color(0x888888)).clone();
        const mt = m.material; if (mt?.map) mt.map.anisotropy = 4;
      }
      ok({grupo: gltf.scene, mallas});
    }, err));
  }
  _registrar(mallas) {
    for (const m of mallas) {
      m.userData.id = this.mallas.length + 1;
      m.userData.idMat = new THREE.ShaderMaterial({vertexShader: VS, fragmentShader: FS_ID, clipping: true, side: THREE.DoubleSide,
        uniforms: {color: {value: new THREE.Color().setRGB(((m.userData.id) & 255) / 255, ((m.userData.id >> 8) & 255) / 255, ((m.userData.id >> 16) & 255) / 255, THREE.NoColorSpace)}}});
      this.mallas.push(m);
      const g = m.geometry; m.userData.tri = Math.round((g.index ? g.index.count : g.attributes.position.count) / 3);
      this.triangulos += m.userData.tri;
    }
  }
  calcularCaja() {
    const c = new THREE.Box3();
    for (const m of this.mallas) { if (!m.geometry.boundingBox) m.geometry.computeBoundingBox(); c.union(m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld)); }
    if (c.isEmpty()) c.set(new THREE.Vector3(-10, -10, -10), new THREE.Vector3(10, 10, 10));
    this.caja.copy(c); return this.caja;
  }
  /** Sustituye el modelo principal. */
  async ponerModelo(buf) {
    this.limpiar();
    const r = await this.cargarGLB(buf);
    this.raiz.add(r.grupo); this._registrar(r.mallas); this.modelo = r.grupo;
    this.calcularCaja(); this.pedir(); return r;
  }
  /** Añade una capa extra (p. ej. «elementos sueltos»). */
  async añadirCapa(nombre, buf, visible = false) {
    const r = await this.cargarGLB(buf);
    r.grupo.visible = visible; r.grupo.name = nombre; this.raiz.add(r.grupo); this._registrar(r.mallas);
    for (const m of r.mallas) m.userData.capa = nombre;
    this.capasExtra.set(nombre, r.grupo); this.pedir(); return r;
  }
  /** Añade objetos de equipos (grupo ya montado); sus mallas son seleccionables. */
  añadirEquipos(grupo, mallas) { this.raiz.add(grupo); this._registrar(mallas); this.pedir(); }

  limpiar() {
    const liberar = o => o.traverse(n => { if (n.isMesh) { n.geometry?.dispose(); (Array.isArray(n.material) ? n.material : [n.material]).forEach(m => { m?.map?.dispose(); m?.dispose(); }); n.userData.idMat?.dispose(); } });
    liberar(this.raiz); this.raiz.clear(); this.mallas.length = 0; this.triangulos = 0; this.capasExtra.clear(); this.modelo = null;
    for (const c of [...this.ayudas.children]) { this.ayudas.remove(c); }
  }

  // ------------------------------------------------------------- corte
  fijarCorte(plano) { this.renderer.clippingPlanes = plano ? [plano] : []; this.pedir(); }

  // ------------------------------------------------------------- selección en GPU
  _con1px(x, y, f) {
    const r = this.renderer, cam = this.camera, el = this.canvas;
    const W = el.clientWidth, H = el.clientHeight;
    if (x < 0 || y < 0 || x >= W || y >= H) return null;
    const prevRT = r.getRenderTarget(), prevBg = this.escena.background, prevEnv = this.escena.environment, c0 = cam.layers.mask;
    const prevCol = r.getClearColor(new THREE.Color()), prevA = r.getClearAlpha(), prevTM = r.toneMapping;
    this.escena.background = null; this.escena.environment = null; r.toneMapping = THREE.NoToneMapping;
    cam.layers.set(0); cam.setViewOffset(W, H, Math.floor(x), Math.floor(y), 1, 1);
    r.setRenderTarget(this.rt); r.setClearColor(0xffffff, 1); r.clear();
    let res = null;
    try { res = f(); r.readRenderTargetPixels(this.rt, 0, 0, 1, 1, this._buf); }
    finally {
      cam.clearViewOffset(); cam.layers.mask = c0; r.setRenderTarget(prevRT); r.setClearColor(prevCol, prevA);
      this.escena.background = prevBg; this.escena.environment = prevEnv; r.toneMapping = prevTM; this.pedir();
    }
    return this._buf;
  }
  /** Punto del mundo bajo el píxel (coordenadas CSS del lienzo) o null si no hay geometría. */
  puntoEn(x, y) {
    this.camera.updateMatrixWorld();
    const b = this._con1px(x, y, () => { this.escena.overrideMaterial = this.matProf; this.renderer.render(this.escena, this.camera); this.escena.overrideMaterial = null; });
    this.escena.overrideMaterial = null;
    if (!b) return null;
    // desempaquetado: dot(enc, 1/(1, 255, 65025, 16581375)) con enc en [0,1)
    const d = (b[0] / 255) + (b[1] / 255) / 255 + (b[2] / 255) / 65025 + (b[3] / 255) / 16581375;
    if (d >= 0.99999) return null;
    const nx = x / this.canvas.clientWidth * 2 - 1, ny = -(y / this.canvas.clientHeight) * 2 + 1;
    return new THREE.Vector3(nx, ny, d * 2 - 1).unproject(this.camera);
  }
  /** Malla bajo el píxel o null. */
  mallaEn(x, y) {
    const guardado = new Map();
    for (const m of this.mallas) { guardado.set(m, m.material); m.material = m.userData.idMat; }
    let b;
    try { b = this._con1px(x, y, () => { this.renderer.render(this.escena, this.camera); }); }
    finally { for (const [m, mt] of guardado) m.material = mt; }
    if (!b || (b[0] === 255 && b[1] === 255 && b[2] === 255)) return null;
    return this.mallas[(b[0] | b[1] << 8 | b[2] << 16) - 1] || null;
  }
}
