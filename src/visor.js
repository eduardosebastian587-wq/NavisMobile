// Visor 3D: render bajo demanda, carga GLB (Draco), selección por GPU (sin raycast), corte y ayudantes.
//
// Dos formatos de modelo:
//  - clásico: una malla por objeto seleccionable;
//  - por elementos (fbx_a_glb_stream.py): pocas mallas grandes (una por color) y un atributo por vértice
//    _FEATURE_ID_0 con el índice del elemento (TAG). Selección, resaltado, ocultar y aislar se resuelven en
//    el shader, así el teléfono dibuja decenas de mallas en vez de miles.
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {DRACOLoader} from 'three/examples/jsm/loaders/DRACOLoader.js';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';

const ATTR = '_feature_id_0';          // nombre que GLTFLoader da a _FEATURE_ID_0
const VIS_W = 1024;                    // ancho de la textura de visibilidad

const PICK_VS = `
#include <common>
#include <clipping_planes_pars_vertex>
#ifdef USE_FID
attribute float ${ATTR};
flat varying float vFid;
#endif
void main() {
  #include <begin_vertex>
  #include <project_vertex>
  #include <clipping_planes_vertex>
  #ifdef USE_FID
  vFid = floor(${ATTR} + 0.5);
  #endif
}`;
const PICK_FS = `
#include <clipping_planes_pars_fragment>
#ifdef USE_FID
uniform sampler2D uVis; uniform float uVisW;
flat varying float vFid;
#endif
void main() {
  #include <clipping_planes_fragment>
  #ifdef USE_FID
  if (texelFetch(uVis, ivec2(int(mod(vFid, uVisW)), int(floor(vFid / uVisW))), 0).r < 0.5) discard;
  #endif
  #ifdef MODO_ID
  float id = vFid + 1.0;
  gl_FragColor = vec4(mod(id, 256.0), mod(floor(id / 256.0), 256.0), floor(id / 65536.0), 255.0) / 255.0;
  #else
  vec4 enc = fract(gl_FragCoord.z * vec4(1.0, 255.0, 65025.0, 16581375.0));
  enc -= enc.yzww * vec4(1.0 / 255.0, 1.0 / 255.0, 1.0 / 255.0, 0.0);
  gl_FragColor = enc;
  #endif
}`;

export class Visor {
  constructor(lienzo, o = {}) {
    this.o = o;
    this.lienzo = lienzo;
    this.renderer = new THREE.WebGLRenderer({canvas: lienzo, antialias: true, powerPreference: 'high-performance'});
    this.renderer.localClippingEnabled = true;
    this.renderer.setClearColor(0x1b1e24);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
    this.camera.layers.enable(1);                       // capa 1 = ayudantes (no entran en la selección)
    this.camera.position.set(60, 50, 60);
    const pm = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x303540, 0.7));
    this.sol = new THREE.DirectionalLight(0xffffff, 1.6); this.sol.position.set(0.5, 1, 0.3);
    this.scene.add(this.sol);

    this.raiz = new THREE.Group(); this.scene.add(this.raiz);
    this.ayudas = new THREE.Group(); this.scene.add(this.ayudas);
    this.mallas = [];          // objetos seleccionables (mallas, o elementos en el formato por elementos)
    this.geo = [];             // mallas reales de la escena
    this.porElementos = false;
    this.seleccion = null;
    this.caja = new THREE.Box3(new THREE.Vector3(-50, -50, -50), new THREE.Vector3(50, 50, 50));
    this.plano = new THREE.Plane(new THREE.Vector3(1, 0, 0), 0);
    this.triangulos = 0;

    this.dracoLoader = new DRACOLoader().setDecoderPath(import.meta.env.BASE_URL + 'draco/');
    this.loader = new GLTFLoader().setDRACOLoader(this.dracoLoader);

    // uniformes compartidos por todos los materiales del formato por elementos
    this.U = {uVis: {value: null}, uVisW: {value: VIS_W}, uSel: {value: -1}};
    this.rtPick = new THREE.WebGLRenderTarget(1, 1, {type: THREE.UnsignedByteType, format: THREE.RGBAFormat});
    const pick = defines => new THREE.ShaderMaterial({vertexShader: PICK_VS, fragmentShader: PICK_FS, clipping: true,
      side: THREE.DoubleSide, defines, uniforms: {uVis: this.U.uVis, uVisW: this.U.uVisW}});
    this.matProf = pick({});
    this.matProfFid = pick({USE_FID: ''});
    this.matIdFid = pick({USE_FID: '', MODO_ID: ''});
    this._sucio = true; this._interactuando = false;
    this._ro = new ResizeObserver(() => this.ajustar());
    this._ro.observe(lienzo.parentElement);
    this.ajustar();
  }

  // ------------------------------------------------------------ render
  pedir() { this._sucio = true; }
  ajustar() {
    const p = this.lienzo.parentElement, w = Math.max(1, p.clientWidth), h = Math.max(1, p.clientHeight);
    this.renderer.setPixelRatio(this._interactuando ? 1 : Math.min(devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h, false);
    this.lienzo.style.width = w + 'px'; this.lienzo.style.height = h + 'px';
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    this._sucio = true;
  }
  interactuando(v) { this._interactuando = v; this.ajustar(); }
  /** Dibuja si hay cambios; devuelve true si dibujó. */
  dibujar() {
    if (!this._sucio) return false;
    this._sucio = false;
    this.renderer.render(this.scene, this.camera);
    return true;
  }

  // ------------------------------------------------------------ carga
  limpiar() {
    this.deseleccionar();
    this.raiz.clear();
    for (const m of this.geo) { m.geometry.dispose(); [].concat(m.material).forEach(x => x.dispose()); }
    this.mallas = []; this.geo = []; this.triangulos = 0; this.porElementos = false; this.cortar(null);
    this.U.uVis.value?.dispose(); this.U.uVis.value = null; this.U.uSel.value = -1;
    this.limpiarAyudas();
  }
  /** elementos: lista del JSON navismobile-elementos-v1 (formato por elementos) o null. */
  async cargar(buffer, elementos = null) {
    this.limpiar();
    const gltf = await new Promise((ok, mal) => this.loader.parse(buffer, '', ok, mal));
    this.raiz.add(gltf.scene);
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse(n => {
      if (!n.isMesh) return;
      for (let p = n.parent; p && p !== gltf.scene; p = p.parent) {
        for (const k in p.userData) if (!(k in n.userData)) n.userData[k] = p.userData[k];
        if (!n.userData.tag && p.name) n.userData.nodo = p.name;
      }
      const g = n.geometry, tri = (g.index ? g.index.count : g.attributes.position.count) / 3;
      n.userData.tri = tri; this.triangulos += tri;
      if (!g.boundingBox) g.computeBoundingBox();
      n.matrixAutoUpdate = false; n.frustumCulled = true;
      this.geo.push(n);
    });
    this.porElementos = !!elementos && this.geo.length > 0 && this.geo.every(m => m.geometry.attributes[ATTR]);
    if (this.porElementos) this._prepararElementos(elementos);
    else this.geo.forEach((m, i) => { m.userData.idx = i; this.mallas.push(m); });
    this.caja = new THREE.Box3().setFromObject(this.raiz);
    if (this.caja.isEmpty()) this.caja.set(new THREE.Vector3(-50, -50, -50), new THREE.Vector3(50, 50, 50));
    this.pedir();
    return {mallas: this.mallas, caja: this.caja, triangulos: this.triangulos};
  }
  _prepararElementos(elementos) {
    const n = elementos.length, H = Math.max(1, Math.ceil(n / VIS_W));
    const tex = new THREE.DataTexture(new Uint8Array(VIS_W * H).fill(255), VIS_W, H, THREE.RedFormat, THREE.UnsignedByteType);
    tex.needsUpdate = true; this.U.uVis.value = tex;
    this.mallas = elementos.map((e, i) => {
      const {min, max, ...datos} = e;
      return {fid: i, name: e.tag, visible: true, material: {color: null},
              caja: new THREE.Box3(new THREE.Vector3(...min), new THREE.Vector3(...max)),
              userData: {...datos, idx: i, tri: e.tri || 0}};
    });
    for (const m of this.geo) {          // color de muestra de cada elemento y shader con identificador
      const f = m.geometry.attributes[ATTR].array, c = m.material.color;
      for (let i = 0; i < f.length; i += 7) { const it = this.mallas[Math.round(f[i])]; if (it && !it.material.color) it.material.color = c; }
      this._inyectar(m.material);
    }
    for (const it of this.mallas) it.material.color ||= new THREE.Color(0x888888);
  }
  _inyectar(mat) {
    const U = this.U;
    mat.onBeforeCompile = sh => {
      Object.assign(sh.uniforms, U);
      sh.vertexShader = `attribute float ${ATTR};\nflat varying float vFid;\n` +
        sh.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>\nvFid = floor(${ATTR} + 0.5);`);
      sh.fragmentShader = 'uniform sampler2D uVis; uniform float uVisW; uniform float uSel;\nflat varying float vFid;\n' +
        sh.fragmentShader
          .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\n' +
            'if (texelFetch(uVis, ivec2(int(mod(vFid, uVisW)), int(floor(vFid / uVisW))), 0).r < 0.5) discard;')
          .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n' +
            'if (abs(vFid - uSel) < 0.5) totalEmissiveRadiance += vec3(0.16, 0.43, 0.69);');
    };
    mat.customProgramCacheKey = () => 'navismobile-fid';
    mat.needsUpdate = true;
  }
  _vis(fid, v) { const t = this.U.uVis.value; t.image.data[fid] = v ? 255 : 0; t.needsUpdate = true; }

  // ------------------------------------------------------------ selección por GPU
  _leer(x, y, pasada) {
    const r = this.renderer, c = this.camera, W = this.lienzo.clientWidth, H = this.lienzo.clientHeight;
    c.setViewOffset(W, H, x, y, 1, 1);
    const antes = {cs: r.outputColorSpace, tm: r.toneMapping};
    r.outputColorSpace = THREE.LinearSRGBColorSpace; r.toneMapping = THREE.NoToneMapping;
    const lay = c.layers.mask; c.layers.set(0);
    const col = r.getClearColor(new THREE.Color()), alfa = r.getClearAlpha();
    r.setClearColor(0xffffff, 1);
    r.setRenderTarget(this.rtPick);
    pasada();
    const buf = new Uint8Array(4);
    r.readRenderTargetPixels(this.rtPick, 0, 0, 1, 1, buf);
    r.setRenderTarget(null);
    r.setClearColor(col, alfa);
    c.layers.mask = lay; c.clearViewOffset();
    r.outputColorSpace = antes.cs; r.toneMapping = antes.tm;
    this._sucio = true;
    return buf;
  }
  _conMaterial(mat) {
    this.scene.overrideMaterial = mat;
    this.renderer.clear(); this.renderer.render(this.scene, this.camera);
    this.scene.overrideMaterial = null;
  }
  /** Punto del mundo bajo el píxel (x, y), o null si no hay geometría. */
  puntoEn(x, y) {
    if (!this.geo.length) return null;
    const b = this._leer(x, y, () => this._conMaterial(this.porElementos ? this.matProfFid : this.matProf));
    const z = (b[0] + b[1] / 255 + b[2] / 65025 + b[3] / 16581375) / 255;
    if (z >= 0.99999) return null;
    const W = this.lienzo.clientWidth, H = this.lienzo.clientHeight;
    return new THREE.Vector3(x / W * 2 - 1, -(y / H) * 2 + 1, z * 2 - 1).unproject(this.camera);
  }
  /** Objeto seleccionable bajo el píxel (x, y), o null. */
  mallaEn(x, y) {
    if (!this.geo.length) return null;
    if (this.porElementos) {
      const b = this._leer(x, y, () => this._conMaterial(this.matIdFid));
      const i = b[0] + (b[1] << 8) + (b[2] << 16);
      return i > 0 && i <= this.mallas.length && !(b[0] === 255 && b[1] === 255 && b[2] === 255) ? this.mallas[i - 1] : null;
    }
    const orig = new Map(), mats = [];
    this.mallas.forEach((m, i) => {
      const c = new THREE.Color(); c.setRGB(((i + 1) & 255) / 255, (((i + 1) >> 8) & 255) / 255, (((i + 1) >> 16) & 255) / 255, THREE.LinearSRGBColorSpace);
      const mat = new THREE.MeshBasicMaterial({color: c, side: THREE.DoubleSide}); mats.push(mat);
      orig.set(m, m.material); m.material = mat;
    });
    const b = this._leer(x, y, () => { this.renderer.clear(); this.renderer.render(this.scene, this.camera); });
    for (const [m, mat] of orig) m.material = mat;
    mats.forEach(m => m.dispose());
    const i = b[0] + (b[1] << 8) + (b[2] << 16);
    return i > 0 && i <= this.mallas.length ? this.mallas[i - 1] : null;
  }

  // ------------------------------------------------------------ selección / visibilidad
  seleccionar(m) {
    this.deseleccionar();
    if (!m) { this.o.alSeleccion?.(null); return; }
    this.seleccion = m;
    if (this.porElementos) this.U.uSel.value = m.fid;
    else {
      m.userData.matOrig = m.material;
      const r = m.material.clone(); r.emissive = new THREE.Color(0x2a6fb0); r.emissiveIntensity = 0.9;
      m.material = r;
    }
    this.o.alSeleccion?.(m); this.pedir();
  }
  deseleccionar() {
    const m = this.seleccion; if (!m) return;
    if (this.porElementos) this.U.uSel.value = -1;
    else { m.material.dispose(); m.material = m.userData.matOrig; delete m.userData.matOrig; }
    this.seleccion = null; this.pedir();
  }
  cajaDe(m) { return m.caja ? m.caja.clone() : new THREE.Box3().setFromObject(m); }
  mostrar(m, v) { m.visible = v; if (this.porElementos) this._vis(m.fid, v); this.pedir(); }
  mostrarTodo() {
    this.mallas.forEach(m => m.visible = true);
    if (this.porElementos) { const t = this.U.uVis.value; t.image.data.fill(255); t.needsUpdate = true; }
    this.pedir();
  }
  aislar(m) {
    this.mallas.forEach(x => x.visible = x === m);
    if (this.porElementos) { const t = this.U.uVis.value; t.image.data.fill(0); t.image.data[m.fid] = 255; t.needsUpdate = true; }
    this.pedir();
  }
  /** Caja del grupo principal de objetos: ignora los muy alejados (líneas largas, piezas sueltas) para encuadrar bien. */
  cajaNucleo() {
    const cajas = this.mallas.filter(m => m.visible).map(m => this.cajaDe(m)).filter(b => !b.isEmpty());
    if (cajas.length < 10) return this.cajaVisible();
    const c = cajas.map(b => b.getCenter(new THREE.Vector3()));
    const med = ['x', 'y', 'z'].map(k => c.map(v => v[k]).sort((a, b) => a - b)[c.length >> 1]);
    const centro = new THREE.Vector3(...med);
    const d = c.map(v => v.distanceTo(centro)), orden = [...d].sort((a, b) => a - b);
    const corte = orden[Math.floor(orden.length * 0.5)] * 2 + 50;
    const r = new THREE.Box3();
    const v = new THREE.Vector3();
    cajas.forEach((b, i) => { if (d[i] <= corte && b.getSize(v).length() <= corte * 2 + 50) r.union(b); });
    return r.isEmpty() ? this.cajaVisible() : r;
  }
  cajaVisible() {
    const b = new THREE.Box3();
    for (const m of this.mallas) if (m.visible) b.union(this.cajaDe(m));
    return b.isEmpty() ? this.caja : b;
  }

  // ------------------------------------------------------------ corte
  /** eje: 'x'|'y'|'z'|null; t en 0..1 sobre la caja; invertir cambia el lado conservado. */
  cortar(eje, t = 0.5, invertir = false) {
    if (!eje) { this.renderer.clippingPlanes = []; this.pedir(); return null; }
    const i = {x: 0, y: 1, z: 2}[eje], n = new THREE.Vector3(); n.setComponent(i, invertir ? 1 : -1);
    const min = this.caja.min.getComponent(i), max = this.caja.max.getComponent(i), pos = min + (max - min) * t;
    this.plano.normal.copy(n); this.plano.constant = invertir ? -pos : pos;
    this.renderer.clippingPlanes = [this.plano];
    this.pedir();
    return pos;
  }

  // ------------------------------------------------------------ ayudantes
  limpiarAyudas() {
    this.ayudas.children.slice().forEach(h => { this.ayudas.remove(h); h.geometry?.dispose(); h.material?.dispose(); });
    this.pivote = null; this.pedir();
  }
  marcaPivote(p, visible) {
    if (!this.pivote) {
      this.pivote = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({color: 0xffd24a, depthTest: false, transparent: true, opacity: 0.9}));
      this.pivote.layers.set(1); this.pivote.renderOrder = 999; this.ayudas.add(this.pivote);
    }
    this.pivote.visible = visible;
    if (visible) {
      this.pivote.position.copy(p);
      this.pivote.scale.setScalar(Math.max(0.01, this.camera.position.distanceTo(p) * 0.008));
    }
    this.pedir();
  }
  linea(a, b) {
    const g = new THREE.BufferGeometry().setFromPoints([a, b]);
    const l = new THREE.Line(g, new THREE.LineBasicMaterial({color: 0xffd24a, depthTest: false}));
    l.layers.set(1); l.renderOrder = 998; this.ayudas.add(l); this.pedir(); return l;
  }
  punto(p) {
    const s = new THREE.Mesh(new THREE.SphereGeometry(1, 10, 8), new THREE.MeshBasicMaterial({color: 0xff6a3d, depthTest: false}));
    s.layers.set(1); s.renderOrder = 999; s.position.copy(p);
    s.scale.setScalar(Math.max(0.01, this.camera.position.distanceTo(p) * 0.006));
    this.ayudas.add(s); this.pedir(); return s;
  }
  aPantalla(p) {
    const v = p.clone().project(this.camera);
    return {x: (v.x + 1) / 2 * this.lienzo.clientWidth, y: (1 - v.y) / 2 * this.lienzo.clientHeight, ok: v.z < 1};
  }
}
